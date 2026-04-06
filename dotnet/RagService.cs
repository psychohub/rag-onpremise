using Microsoft.Extensions.Options;
using RagOnPremise.Models;
using System.Text.Json.Serialization;

namespace RagOnPremise.Services
{
    /// <summary>
    /// Servicio RAG que orquesta el flujo completo:
    /// Pregunta → Embedding → Búsqueda Qdrant → Prompt → LLM → Respuesta
    ///
    /// Incluye caché semántico para respuestas instantáneas en la segunda consulta.
    /// </summary>
    public class RagService : IRagService
    {
        private readonly RagSettings _settings;
        private readonly ILogger<RagService> _logger;

        // ── Caché semántico ───────────────────────────────────────────────────
        private static readonly List<SemanticCacheEntry> _cache = new();
        private static readonly SemaphoreSlim _cacheLock = new(1, 1);
        private const float SIMILARITY_THRESHOLD = 0.92f;
        private const int CACHE_MAX_ENTRIES = 200;
        private static readonly TimeSpan CACHE_TTL = TimeSpan.FromHours(24);

        public RagService(IOptions<RagSettings> settings, ILogger<RagService> logger)
        {
            _settings = settings.Value;
            _logger = logger;
        }

        // ── Consulta principal ────────────────────────────────────────────────

        public async Task<RagQueryResponse> QueryAsync(RagQueryRequest request)
        {
            try
            {
                // 1. Generar embedding de la pregunta
                var embedding = await GetEmbeddingAsync(request.Question);

                // 2. Buscar en caché semántico
                var (cacheHit, cachedResponse) = await SearchCacheAsync(
                    embedding, request.Question);

                if (cacheHit && cachedResponse != null)
                    return cachedResponse;

                // 3. Buscar chunks relevantes en Qdrant
                var collection = request.Collection ?? _settings.CollectionName;
                var sources = await SearchQdrantAsync(embedding, collection);

                // 4. Construir contexto con los chunks
                var context = string.Join("\n\n", sources.Select(s => s.Text));

                // 5. Generar respuesta con el LLM
                var answer = await GenerateAnswerAsync(request.Question, context);

                var response = new RagQueryResponse
                {
                    Answer = answer,
                    Sources = sources
                };

                // 6. Guardar en caché para futuras consultas similares
                await SaveToCacheAsync(embedding, request.Question, response);

                return response;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error en RAG query: {Question}", request.Question);
                throw;
            }
        }

        public async Task<bool> TestConnectionAsync()
        {
            try
            {
                using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(5) };
                var response = await client.GetAsync(_settings.OllamaUrl);
                return response.IsSuccessStatusCode;
            }
            catch { return false; }
        }

        // ── Embedding ─────────────────────────────────────────────────────────

        private async Task<float[]> GetEmbeddingAsync(string text)
        {
            var payload = new { model = _settings.EmbeddingModel, prompt = text };
            var json = System.Text.Json.JsonSerializer.Serialize(payload);
            var content = new StringContent(json, System.Text.Encoding.UTF8, "application/json");

            using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(30) };
            var response = await client.PostAsync(
                $"{_settings.OllamaUrl}/api/embeddings", content);
            response.EnsureSuccessStatusCode();

            var result = await response.Content
                .ReadFromJsonAsync<EmbeddingResponse>();
            return result?.Embedding ?? Array.Empty<float>();
        }

        // ── Búsqueda en Qdrant ────────────────────────────────────────────────
        // IMPORTANTE: Usar siempre HttpClient REST directo.
        // El SDK oficial de Qdrant para .NET usa gRPC y falla con HTTP/1.1

        private async Task<List<RagSource>> SearchQdrantAsync(
            float[] embedding, string collection)
        {
            var payload = new
            {
                vector = embedding,
                limit = _settings.MaxResults,
                with_payload = true,
                with_vectors = false
            };

            var json = System.Text.Json.JsonSerializer.Serialize(payload);
            var content = new StringContent(json,
                System.Text.Encoding.UTF8, "application/json");

            using var client = new HttpClient { Timeout = TimeSpan.FromSeconds(10) };
            var response = await client.PostAsync(
                $"{_settings.QdrantUrl}/collections/{collection}/points/search",
                content);
            response.EnsureSuccessStatusCode();

            var resultJson = await response.Content.ReadAsStringAsync();
            var result = System.Text.Json.JsonSerializer
                .Deserialize<QdrantSearchResponse>(resultJson);

            return result?.Result?.Select(r => new RagSource
            {
                Filename = r.Payload.GetValueOrDefault("filename")?.ToString() ?? "",
                Text = r.Payload.GetValueOrDefault("text")?.ToString() ?? "",
                Score = r.Score
            }).ToList() ?? new List<RagSource>();
        }

        // ── Generación con LLM ────────────────────────────────────────────────
        // IMPORTANTE: Mistral en CPU tarda 60-120 segundos.
        // El timeout por defecto de HttpClient (100s) no alcanza.
        // Configurar explícitamente 300 segundos.

        private async Task<string> GenerateAnswerAsync(string question, string context)
        {
            var prompt = $"""
                Eres un asistente especializado en documentos institucionales.

                INSTRUCCIONES:
                1. Analiza el contexto proporcionado y responde la pregunta basándote en él.
                2. Si el contexto contiene información relevante aunque sea parcial, úsala.
                3. Responde siempre en español de forma clara y concisa.
                4. Solo si el contexto NO contiene absolutamente ninguna información
                   relacionada con la pregunta, responde exactamente:
                   "No encontré información sobre ese tema en los documentos disponibles."
                5. No inventes datos, nombres, fechas ni referencias que no estén en el contexto.

                Contexto de los documentos:
                {context}

                Pregunta: {question}

                Respuesta:
                """;

            var payload = new
            {
                model = _settings.ChatModel,
                prompt = prompt,
                stream = false
            };

            var json = System.Text.Json.JsonSerializer.Serialize(payload);
            var content = new StringContent(json,
                System.Text.Encoding.UTF8, "application/json");

            // Timeout de 300s — Mistral en CPU puede tardar 60-120s
            using var client = new HttpClient
            {
                Timeout = TimeSpan.FromSeconds(300)
            };

            var response = await client.PostAsync(
                $"{_settings.OllamaUrl}/api/generate", content);
            response.EnsureSuccessStatusCode();

            var result = await response.Content
                .ReadFromJsonAsync<OllamaGenerateResponse>();
            return result?.Response ?? "No se pudo generar respuesta.";
        }

        // ── Caché semántico ───────────────────────────────────────────────────

        private async Task<(bool found, RagQueryResponse? response)>
            SearchCacheAsync(float[] embedding, string question)
        {
            await _cacheLock.WaitAsync();
            try
            {
                var now = DateTime.UtcNow;
                _cache.RemoveAll(e => now - e.CreatedAt > CACHE_TTL);

                foreach (var entry in _cache)
                {
                    float similarity = CosineSimilarity(embedding, entry.Embedding);

                    if (similarity >= SIMILARITY_THRESHOLD)
                    {
                        _logger.LogInformation(
                            "[Cache HIT] Similitud: {Sim:F4} | Original: {Q}",
                            similarity, entry.OriginalQuestion);

                        return (true, new RagQueryResponse
                        {
                            Answer = entry.Answer,
                            Sources = entry.Sources
                        });
                    }
                }
                return (false, null);
            }
            finally { _cacheLock.Release(); }
        }

        private async Task SaveToCacheAsync(
            float[] embedding, string question, RagQueryResponse response)
        {
            await _cacheLock.WaitAsync();
            try
            {
                if (_cache.Count >= CACHE_MAX_ENTRIES)
                    _cache.RemoveAt(0);

                _cache.Add(new SemanticCacheEntry
                {
                    Embedding = embedding,
                    Answer = response.Answer,
                    Sources = response.Sources,
                    OriginalQuestion = question,
                    CreatedAt = DateTime.UtcNow
                });

                _logger.LogInformation("[Cache SAVE] Entradas: {Count}", _cache.Count);
            }
            finally { _cacheLock.Release(); }
        }

        private static float CosineSimilarity(float[] a, float[] b)
        {
            if (a.Length != b.Length) return 0f;
            float dot = 0, normA = 0, normB = 0;
            for (int i = 0; i < a.Length; i++)
            {
                dot += a[i] * b[i];
                normA += a[i] * a[i];
                normB += b[i] * b[i];
            }
            float denom = MathF.Sqrt(normA) * MathF.Sqrt(normB);
            return denom == 0 ? 0f : dot / denom;
        }

        // ── Administración del caché ──────────────────────────────────────────

        public static void ClearCache()
        {
            _cacheLock.Wait();
            try { _cache.Clear(); }
            finally { _cacheLock.Release(); }
        }

        public static object GetCacheStats() => new
        {
            total_entries = _cache.Count,
            oldest_entry = _cache.Count > 0 ? _cache.Min(e => e.CreatedAt) : (DateTime?)null,
            ttl_hours = CACHE_TTL.TotalHours,
            max_entries = CACHE_MAX_ENTRIES,
            similarity_threshold = SIMILARITY_THRESHOLD
        };
    }

    // ── Clases auxiliares ─────────────────────────────────────────────────────

    internal class SemanticCacheEntry
    {
        public float[] Embedding { get; set; } = Array.Empty<float>();
        public string Answer { get; set; } = string.Empty;
        public List<RagSource> Sources { get; set; } = new();
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
        public string OriginalQuestion { get; set; } = string.Empty;
    }

    internal class EmbeddingResponse
    {
        [JsonPropertyName("embedding")]
        public float[] Embedding { get; set; } = Array.Empty<float>();
    }

    internal class OllamaGenerateResponse
    {
        [JsonPropertyName("response")]
        public string Response { get; set; } = string.Empty;
    }

    internal class QdrantSearchResponse
    {
        [JsonPropertyName("result")]
        public List<QdrantSearchResult> Result { get; set; } = new();
    }

    internal class QdrantSearchResult
    {
        [JsonPropertyName("score")]
        public double Score { get; set; }

        [JsonPropertyName("payload")]
        public Dictionary<string, object> Payload { get; set; } = new();
    }
}
