using Microsoft.Extensions.Options;
using RagOnPremise.Models;
using System.Collections.Concurrent;
using System.Text.Json.Serialization;

namespace RagOnPremise.Services
{
    /// <summary>
    /// Servicio RAG que orquesta el flujo completo:
    /// Pregunta → Embedding → Búsqueda Qdrant → Prompt → LLM → Respuesta
    ///
    /// Incluye caché semántico particionado por colección, modelos y prompt version.
    /// Propaga CancellationToken para liberar recursos si el cliente desconecta.
    /// </summary>
    public class RagService : IRagService
    {
        private readonly RagSettings _settings;
        private readonly ILogger<RagService> _logger;
        private readonly IHttpClientFactory _httpClientFactory;

        // ── Caché semántico ───────────────────────────────────────────────────
        // Particionado por (collection, embeddingModel, chatModel, promptVersion, topK).
        // Esto elimina el vector de fuga cross-collection: la similitud coseno
        // solo se calcula DENTRO de un mismo namespace.
        private static readonly ConcurrentDictionary<string, List<SemanticCacheEntry>> _cache = new();
        private static readonly SemaphoreSlim _cacheLock = new(1, 1);
        private const float SIMILARITY_THRESHOLD = 0.92f;
        private const int CACHE_MAX_ENTRIES_PER_PARTITION = 200;
        private static readonly TimeSpan CACHE_TTL = TimeSpan.FromHours(24);

        // Versión del prompt. Incrementar al cambiar el template.
        // Al cambiar, las entradas viejas del caché quedan en un namespace
        // distinto y dejan de servirse — no hace falta borrar manualmente.
        private const string PROMPT_VERSION = "v1";

        public RagService(
            IOptions<RagSettings> settings,
            IHttpClientFactory httpClientFactory,
            ILogger<RagService> logger)
        {
            _settings = settings.Value;
            _httpClientFactory = httpClientFactory;
            _logger = logger;
        }

        // ── Consulta principal ────────────────────────────────────────────────

        public async Task<RagQueryResponse> QueryAsync(
            RagQueryRequest request,
            CancellationToken cancellationToken = default)
        {
            try
            {
                var collection = request.Collection ?? _settings.CollectionName;

                // 1. Generar embedding de la pregunta
                var embedding = await GetEmbeddingAsync(request.Question, cancellationToken);

                // 2. Construir la key del namespace del caché
                var cacheKey = BuildCacheKey(collection);

                // 3. Buscar en caché semántico (limitado al namespace)
                if (_settings.SemanticCacheEnabled)
                {
                    var (cacheHit, cachedResponse) = await SearchCacheAsync(
                        cacheKey, embedding, request.Question, cancellationToken);

                    if (cacheHit && cachedResponse != null)
                        return cachedResponse;
                }

                // 4. Buscar chunks relevantes en Qdrant
                var sources = await SearchQdrantAsync(embedding, collection, cancellationToken);

                // 5. Construir contexto con los chunks
                var context = string.Join("\n\n", sources.Select(s => s.Text));

                // 6. Generar respuesta con el LLM
                var answer = await GenerateAnswerAsync(request.Question, context, cancellationToken);

                var response = new RagQueryResponse
                {
                    Answer = answer,
                    Sources = sources
                };

                // 7. Guardar en el namespace correcto del caché
                if (_settings.SemanticCacheEnabled)
                {
                    await SaveToCacheAsync(
                        cacheKey, embedding, request.Question, response, cancellationToken);
                }

                return response;
            }
            catch (OperationCanceledException)
            {
                _logger.LogInformation(
                    "RAG query cancelada por el cliente: {Question}", request.Question);
                throw;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Error en RAG query: {Question}", request.Question);
                throw;
            }
        }

        public async Task<bool> TestConnectionAsync(CancellationToken cancellationToken = default)
        {
            try
            {
                var client = _httpClientFactory.CreateClient("ollama-embedding");
                var response = await client.GetAsync(_settings.OllamaUrl, cancellationToken);
                return response.IsSuccessStatusCode;
            }
            catch { return false; }
        }

        // ── Cache key ─────────────────────────────────────────────────────────
        //
        // La key define el "namespace" del caché. Dos entradas con la misma
        // similitud semántica pero distinta key nunca se comparten.
        //
        // Componentes:
        //   - collection: para no filtrar respuestas de una colección
        //     en consultas a otra.
        //   - embeddingModel: si cambia el modelo de embeddings, los vectores
        //     viejos no son comparables con los nuevos.
        //   - chatModel: si cambia el LLM, las respuestas viejas fueron
        //     generadas por otro modelo — no queremos que sigan sirviéndose.
        //   - promptVersion: si cambia el template del prompt, cambia la
        //     naturaleza de la respuesta esperada.
        //   - topK: cambia cuántos chunks se recuperan, por tanto la respuesta.

        private string BuildCacheKey(string collection)
        {
            return string.Join("|",
                collection,
                _settings.EmbeddingModel,
                _settings.ChatModel,
                PROMPT_VERSION,
                $"k={_settings.MaxResults}");
        }

        // ── Embedding ─────────────────────────────────────────────────────────

        private async Task<float[]> GetEmbeddingAsync(
            string text, CancellationToken cancellationToken)
        {
            var payload = new { model = _settings.EmbeddingModel, prompt = text };
            var json = System.Text.Json.JsonSerializer.Serialize(payload);
            var content = new StringContent(
                json, System.Text.Encoding.UTF8, "application/json");

            var client = _httpClientFactory.CreateClient("ollama-embedding");
            var response = await client.PostAsync(
                $"{_settings.OllamaUrl}/api/embeddings", content, cancellationToken);
            response.EnsureSuccessStatusCode();

            var result = await response.Content
                .ReadFromJsonAsync<EmbeddingResponse>(cancellationToken: cancellationToken);
            return result?.Embedding ?? Array.Empty<float>();
        }

        // ── Búsqueda en Qdrant ────────────────────────────────────────────────
        // IMPORTANTE: Usar siempre HttpClient REST directo.
        // El SDK oficial de Qdrant para .NET usa gRPC y falla con HTTP/1.1.

        private async Task<List<RagSource>> SearchQdrantAsync(
            float[] embedding, string collection, CancellationToken cancellationToken)
        {
            var payload = new
            {
                vector = embedding,
                limit = _settings.MaxResults,
                with_payload = true,
                with_vectors = false
            };

            var json = System.Text.Json.JsonSerializer.Serialize(payload);
            var content = new StringContent(
                json, System.Text.Encoding.UTF8, "application/json");

            var client = _httpClientFactory.CreateClient("qdrant");
            var response = await client.PostAsync(
                $"{_settings.QdrantUrl}/collections/{collection}/points/search",
                content, cancellationToken);
            response.EnsureSuccessStatusCode();

            var resultJson = await response.Content.ReadAsStringAsync(cancellationToken);
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
        // El cliente "ollama-generation" debe registrarse con Timeout = 300s
        // — ver el snippet de registro en el README, sección "Integrar en tu
        // API .NET". Si el nombre no está registrado, IHttpClientFactory
        // devuelve un cliente con el default de 100s y la generación se corta.
        // Además, propagamos CancellationToken para liberar recursos si el
        // cliente desconecta durante la generación.

        private async Task<string> GenerateAnswerAsync(
            string question, string context, CancellationToken cancellationToken)
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
            var content = new StringContent(
                json, System.Text.Encoding.UTF8, "application/json");

            var client = _httpClientFactory.CreateClient("ollama-generation");
            var response = await client.PostAsync(
                $"{_settings.OllamaUrl}/api/generate", content, cancellationToken);
            response.EnsureSuccessStatusCode();

            var result = await response.Content
                .ReadFromJsonAsync<OllamaGenerateResponse>(cancellationToken: cancellationToken);
            return result?.Response ?? "No se pudo generar respuesta.";
        }

        // ── Caché semántico ───────────────────────────────────────────────────

        private async Task<(bool found, RagQueryResponse? response)>
            SearchCacheAsync(
                string cacheKey,
                float[] embedding,
                string question,
                CancellationToken cancellationToken)
        {
            await _cacheLock.WaitAsync(cancellationToken);
            try
            {
                if (!_cache.TryGetValue(cacheKey, out var partition))
                    return (false, null);

                var now = DateTime.UtcNow;
                partition.RemoveAll(e => now - e.CreatedAt > CACHE_TTL);

                foreach (var entry in partition)
                {
                    float similarity = CosineSimilarity(embedding, entry.Embedding);

                    if (similarity >= SIMILARITY_THRESHOLD)
                    {
                        _logger.LogInformation(
                            "[Cache HIT] Namespace: {Key} | Similitud: {Sim:F4} | Original: {Q}",
                            cacheKey, similarity, entry.OriginalQuestion);

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
            string cacheKey,
            float[] embedding,
            string question,
            RagQueryResponse response,
            CancellationToken cancellationToken)
        {
            await _cacheLock.WaitAsync(cancellationToken);
            try
            {
                var partition = _cache.GetOrAdd(cacheKey, _ => new List<SemanticCacheEntry>());

                if (partition.Count >= CACHE_MAX_ENTRIES_PER_PARTITION)
                    partition.RemoveAt(0);

                partition.Add(new SemanticCacheEntry
                {
                    Embedding = embedding,
                    Answer = response.Answer,
                    Sources = response.Sources,
                    OriginalQuestion = question,
                    CreatedAt = DateTime.UtcNow
                });

                _logger.LogInformation(
                    "[Cache SAVE] Namespace: {Key} | Entradas en partición: {Count}",
                    cacheKey, partition.Count);
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
            total_partitions = _cache.Count,
            total_entries = _cache.Values.Sum(p => p.Count),
            ttl_hours = CACHE_TTL.TotalHours,
            max_entries_per_partition = CACHE_MAX_ENTRIES_PER_PARTITION,
            similarity_threshold = SIMILARITY_THRESHOLD,
            prompt_version = PROMPT_VERSION
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
