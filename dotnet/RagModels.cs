namespace RagOnPremise.Models
{
    /// <summary>Request para consultar el RAG.</summary>
    public class RagQueryRequest
    {
        /// <summary>Pregunta del usuario en lenguaje natural.</summary>
        public string Question { get; set; } = string.Empty;

        /// <summary>Colección a consultar. Si es null usa la configurada por defecto.</summary>
        public string? Collection { get; set; }
    }

    /// <summary>Respuesta del RAG con la respuesta generada y las fuentes.</summary>
    public class RagQueryResponse
    {
        /// <summary>Respuesta generada por el LLM basada en el contexto.</summary>
        public string Answer { get; set; } = string.Empty;

        /// <summary>Fragmentos de documentos usados como contexto.</summary>
        public List<RagSource> Sources { get; set; } = new();
    }

    /// <summary>Fragmento de documento usado como fuente.</summary>
    public class RagSource
    {
        /// <summary>Nombre del archivo de origen.</summary>
        public string Filename { get; set; } = string.Empty;

        /// <summary>Fragmento de texto relevante.</summary>
        public string Text { get; set; } = string.Empty;

        /// <summary>Puntuación de similitud (0-1). Mayor = más relevante.</summary>
        public double Score { get; set; }
    }
}
