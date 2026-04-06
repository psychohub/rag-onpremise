using Microsoft.AspNetCore.Mvc;
using RagOnPremise.Models;
using RagOnPremise.Services;

namespace RagOnPremise.Controllers
{
    /// <summary>
    /// Controlador RAG — expone endpoints para consultar documentos.
    ///
    /// Endpoints:
    ///   POST /Rag/query        — consultar documentos con lenguaje natural
    ///   GET  /Rag/test         — verificar conexión con Ollama
    ///   GET  /Rag/cache/stats  — estadísticas del caché semántico
    ///   DELETE /Rag/cache/clear — limpiar caché (usar al cambiar modelo LLM)
    /// </summary>
    [ApiController]
    [Route("[controller]")]
    public class RagController : ControllerBase
    {
        private readonly IRagService _ragService;
        private readonly ILogger<RagController> _logger;

        public RagController(IRagService ragService, ILogger<RagController> logger)
        {
            _ragService = ragService;
            _logger = logger;
        }

        /// <summary>
        /// Consulta documentos usando lenguaje natural.
        /// El servicio busca los fragmentos más relevantes y genera una respuesta contextual.
        /// </summary>
        [HttpPost("query")]
        public async Task<IActionResult> Query([FromBody] RagQueryRequest request)
        {
            if (string.IsNullOrWhiteSpace(request.Question))
                return BadRequest("La pregunta no puede estar vacía.");

            _logger.LogInformation("RAG query: {Question}", request.Question);

            var response = await _ragService.QueryAsync(request);
            return Ok(response);
        }

        /// <summary>
        /// Verifica que Ollama esté disponible y respondiendo.
        /// </summary>
        [HttpGet("test")]
        public async Task<IActionResult> Test()
        {
            var connected = await _ragService.TestConnectionAsync();
            return Ok(new
            {
                connected,
                message = connected ? "Ollama conectado" : "Sin conexión con Ollama"
            });
        }

        /// <summary>
        /// Retorna estadísticas del caché semántico.
        /// </summary>
        [HttpGet("cache/stats")]
        public IActionResult CacheStats()
        {
            return Ok(new { stats = RagService.GetCacheStats() });
        }

        /// <summary>
        /// Limpia el caché semántico.
        /// IMPORTANTE: Ejecutar siempre al cambiar el modelo LLM en appsettings.json.
        /// </summary>
        [HttpDelete("cache/clear")]
        public IActionResult ClearCache()
        {
            RagService.ClearCache();
            _logger.LogInformation("Cache RAG limpiado.");
            return Ok(new { message = "Cache limpiado correctamente." });
        }
    }
}
