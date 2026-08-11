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

        /// <summary>
        /// Habilita el caché semántico. Default: false.
        ///
        /// ADVERTENCIA DE SEGURIDAD: El caché semántico sirve respuestas previamente
        /// generadas cuando el embedding de la nueva pregunta está cerca de una
        /// consulta cacheada (similitud coseno sobre SIMILARITY_THRESHOLD, la
        /// constante 0.92f de RagService — no es una clave de configuración:
        /// cambiarla requiere editar el código y recompilar).
        /// Pruebas empíricas con nomic-embed-text sobre texto administrativo español
        /// muestran que esto es INSEGURO en esa combinación: pares adversos
        /// (negaciones, cambios de entidad, cambios temporales) alcanzan similitud
        /// coseno de hasta 0.9984, mientras que paráfrasis genuinas se quedan bajo
        /// 0.91. Un hit del caché nunca llega al LLM, por lo que las respuestas
        /// incorrectas se sirven silenciosamente.
        ///
        /// Habilitar solo si se ha verificado que el caché es seguro para el corpus
        /// y modelo de embeddings específicos. Ver docs/experiments/threshold-safety.md
        /// </summary>
        public bool SemanticCacheEnabled { get; set; } = false;
    }
}
