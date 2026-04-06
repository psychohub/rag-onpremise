namespace RagOnPremise.Models
{
    /// <summary>
    /// Configuración del módulo RAG.
    /// Se lee desde appsettings.json sección "RagSettings".
    /// </summary>
    public class RagSettings
    {
        /// <summary>URL de Qdrant. Ejemplo: http://localhost:6333</summary>
        public string QdrantUrl { get; set; } = "http://localhost:6333";

        /// <summary>URL de Ollama. Ejemplo: http://localhost:11434</summary>
        public string OllamaUrl { get; set; } = "http://localhost:11434";

        /// <summary>Nombre de la colección en Qdrant.</summary>
        public string CollectionName { get; set; } = "mis-documentos";

        /// <summary>Modelo de embeddings. Recomendado: nomic-embed-text</summary>
        public string EmbeddingModel { get; set; } = "nomic-embed-text";

        /// <summary>Modelo de chat. Opciones: mistral, phi3:mini, llama3.2:3b</summary>
        public string ChatModel { get; set; } = "mistral";

        /// <summary>Cantidad de chunks a recuperar de Qdrant por consulta.</summary>
        public int MaxResults { get; set; } = 5;
    }
}
