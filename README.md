# RAG On-Premise con Ollama, Qdrant y ASP.NET

> **Tus documentos se quedan en tu servidor. Siempre.**

Sistema RAG (Retrieval-Augmented Generation) completamente local para consultar documentos institucionales sin enviar información a la nube.



---

## 🎯 Problema que resuelve

Imagina esta situación: Tu institución tiene miles de documentos normativos, circulares, lineamientos y manuales. Los funcionarios pierden horas buscando información.

> "¿En qué circular dice que el procedimiento X requiere el formulario Y?"

Podrías usar ChatGPT o Claude... pero eso significa **enviar documentos institucionales a servidores externos**. En muchas organizaciones eso no es aceptable por razones de privacidad, seguridad o regulación.

## ✅ Solución: RAG completamente local

Este repositorio es una implementación de referencia de un **asistente de documentos on-premise** con tres pilares:

### 1️⃣ Privacidad total
- Los documentos **nunca salen** del servidor
- El modelo de IA corre localmente con Ollama
- Sin API Keys de terceros, sin suscripciones

### 2️⃣ Búsqueda semántica
- Entiende el significado de las preguntas, no solo palabras clave
- "¿Qué dice el reglamento sobre vacaciones?" encuentra documentos aunque no digan exactamente esas palabras

### 3️⃣ Respuestas contextuales
- El modelo solo responde con lo que está en **tus documentos**
- Si la información no existe, lo indica honestamente
- Cita las fuentes exactas de cada respuesta

---

## 🚀 Demo en acción

```
Usuario: ¿Cuáles son los requisitos para solicitar un permiso?

Asistente: Según el Manual de Procedimientos (sección 4.2),
los requisitos son:
1. Formulario F-001 debidamente completado
2. Aprobación del jefe inmediato
3. Presentar con 5 días hábiles de anticipación

Fuentes: Manual_Procedimientos_v3.pdf (score: 0.94)
```

---

## 🛠️ Stack tecnológico

| Componente | Tecnología | Descripción |
|-----------|-----------|-------------|
| Motor LLM | Ollama + Mistral 7B | Genera las respuestas |
| Embeddings | nomic-embed-text | Convierte texto a vectores |
| Vector DB | Qdrant 1.17+ | Almacena y busca vectores |
| Ingesta | Python 3.11+ | Procesa PDFs, Word, Excel |
| API | ASP.NET Core 9 | Orquesta el flujo RAG |
| Interfaz | ASP.NET WebForms | Chat integrado (opcional) |

Todo corre en **Windows Server**, sin Docker, sin GPU.

---

## 📂 Estructura del repositorio

```
rag-onpremise/
├── python/
│   ├── ingestor.py          # Servicio de ingesta de documentos
│   ├── config.example.json  # Configuración de ejemplo
│   └── requirements.txt     # Dependencias Python
├── dotnet/
│   ├── RagController.cs     # Controlador ASP.NET Core
│   ├── RagService.cs        # Servicio con caché semántico
│   ├── RagModels.cs         # DTOs
│   └── RagSettings.cs       # Configuración tipada
├── docs/
│   ├── instalacion.md       # Guía de instalación paso a paso
│   ├── problemas-comunes.md # Troubleshooting
│   ├── adr/                 # Decisiones de diseño (ver adr/README.md)
│   └── experiments/         # Experimentos y sus scripts reproducibles
└── README.md
```

---

## ⚡ Inicio rápido

### 1. Instalar Ollama

```powershell
# Descargar desde https://ollama.com/download/windows
# Después de instalar, descargar los modelos:
ollama pull mistral
ollama pull nomic-embed-text
```

⚠️ **Crítico:** Por defecto Ollama solo escucha en localhost.
Si otros servidores necesitan conectarse:

```powershell
$env:OLLAMA_HOST = "0.0.0.0:11434"
ollama serve
```

### 2. Instalar Qdrant

```powershell
# Descargar binario desde https://github.com/qdrant/qdrant/releases
# Extraer en C:\Services\Qdrant\
# Ejecutar:
C:\Services\Qdrant\qdrant.exe
# Verificar: http://localhost:6333
```

### 3. Instalar Python e ingestor

```powershell
# Crear entorno virtual
python -m venv venv
.\venv\Scripts\Activate.ps1

# Instalar dependencias
pip install -r python/requirements.txt

# Configurar
copy python/config.example.json python/config.json
# Editar config.json con tus rutas

# Ejecutar ingesta inicial
python python/ingestor.py
```

### 4. Integrar en tu API .NET

Copiar los archivos de `dotnet/` a tu proyecto y registrar en `Program.cs`:

```csharp
builder.Services.Configure<RagSettings>(
    builder.Configuration.GetSection("RagSettings"));

// Los tres clientes nombrados que RagService pide por nombre.
// Los nombres deben coincidir carácter por carácter con los de
// CreateClient(...) en RagService.cs. Si uno no está registrado,
// IHttpClientFactory no lanza excepción: devuelve un cliente con
// settings por defecto, incluido Timeout de 100 segundos.
builder.Services.AddHttpClient("ollama-embedding",
    c => c.Timeout = TimeSpan.FromSeconds(30));
builder.Services.AddHttpClient("ollama-generation",
    c => c.Timeout = TimeSpan.FromSeconds(300));
builder.Services.AddHttpClient("qdrant",
    c => c.Timeout = TimeSpan.FromSeconds(10));

builder.Services.AddScoped<IRagService, RagService>();
```

Agregar en `appsettings.json`:

Ver la configuración completa de `RagSettings` en la sección 
[Configuración](#configuración) más abajo.

---

## Configuración

El proyecto tiene **dos archivos de configuración independientes** — 
uno para el ingestor Python y otro para la API .NET. Comparten cuatro 
claves que deben mantenerse sincronizadas manualmente, o el sistema 
falla en silencio (el ingestor guarda en una colección o modelo distinto 
al que la API busca).

### Ingestor Python — `python/config.json`

Copiar `python/config.example.json` como `python/config.json` y ajustar:

```json
{
  "documents_folder": "C:\\MisDocumentos\\ParaIndexar",
  "qdrant_url": "http://localhost:6333",
  "ollama_url": "http://localhost:11434",
  "collection_name": "mis-documentos",
  "embedding_model": "nomic-embed-text",
  "chunk_size": 500,
  "chunk_overlap": 50
}
```

### API .NET — sección `RagSettings` de `appsettings.json`

```json
{
  "RagSettings": {
    "QdrantUrl": "http://localhost:6333",
    "OllamaUrl": "http://localhost:11434",
    "CollectionName": "mis-documentos",
    "EmbeddingModel": "nomic-embed-text",
    "ChatModel": "mistral",
    "MaxResults": 5,
    "SemanticCacheEnabled": false
  }
}
```

Ver [advertencia sobre `SemanticCacheEnabled`](#caché-semántico-desactivado-por-defecto) 
más abajo.

### ⚠️ Claves compartidas — sincronización manual

Cuatro claves deben tener **el mismo valor** en los dos archivos, o el 
retrieval falla silenciosamente:

| Ingestor Python | API .NET |
|---|---|
| `qdrant_url` | `QdrantUrl` |
| `ollama_url` | `OllamaUrl` |
| `collection_name` | `CollectionName` |
| `embedding_model` | `EmbeddingModel` |

Si cambiás una en un lado, cambiala en el otro. No hay verificación 
automática de sincronización.

---

## 🏗️ Arquitectura

```
Documentos (PDF/Word/Excel)
    ↓
[Ingestor Python]
    ├── Extrae texto (pdfplumber, python-docx, openpyxl)
    ├── Divide en chunks (500 tokens, 50 overlap)
    ├── Genera embeddings (nomic-embed-text via Ollama)
    └── Almacena en Qdrant
    
Usuario hace una pregunta
    ↓
[ASP.NET API - RagService]
    ├── 1. Generar embedding de la pregunta
    ├── 2. Buscar chunks similares en Qdrant (cosine similarity)
    ├── 3. Construir prompt con contexto
    ├── 4. Llamar a Mistral via Ollama
    └── 5. Retornar respuesta + fuentes citadas
```

---

## ⚠️ Lecciones aprendidas (las que duelen)

### 1. Qdrant SDK usa gRPC — usar REST directo

```csharp
// ❌ El SDK de .NET usa gRPC y falla con Qdrant en HTTP/1.1
// var client = new QdrantClient(new Uri(url));

// ✅ HttpClient REST directo
var response = await _httpClient.PostAsync(
    $"{qdrantUrl}/collections/{collection}/points/search",
    content);
```

### 2. Timeout de HttpClient mata las respuestas

El default de `HttpClient` es 100 segundos y Mistral en CPU tarda 60-120.
La generación muere a mitad de camino con `TaskCanceledException`.

`RagService` no construye `HttpClient` a mano: pide clientes nombrados a
`IHttpClientFactory`. El timeout se configura al registrarlos, no en el
punto de uso.

```csharp
// ❌ Nombre que nadie pide → los que sí se piden quedan sin registrar,
//    y un nombre sin registrar devuelve un cliente con Timeout de 100s.
//    IHttpClientFactory no lanza excepción: el cliente funciona hasta
//    que la generación pasa de 100 segundos.
builder.Services.AddHttpClient("ollama");

// ✅ Registrar cada nombre que el servicio pide, con su timeout
builder.Services.AddHttpClient("ollama-generation",
    c => c.Timeout = TimeSpan.FromSeconds(300));
```

Los tres nombres del registro deben coincidir carácter por carácter con
los de `CreateClient(...)` en `RagService.cs` — registro completo en
[Integrar en tu API .NET](#4-integrar-en-tu-api-net). No hay verificación
en tiempo de compilación: un typo en el nombre produce silenciosamente un
cliente con el default de 100 segundos.

### 3. Ollama no acepta conexiones externas por defecto

```powershell
# ❌ Solo escucha en 127.0.0.1
ollama serve

# ✅ Escuchar en todas las interfaces
$env:OLLAMA_HOST = "0.0.0.0:11434"
ollama serve
```

### 4. Python MSI puede fallar con GPO corporativas

Usar el **paquete embebible** de Python:
- Descargar `python-3.x.x-amd64-embed.zip`
- Descomentar `import site` en `python3xx._pth`
- Instalar pip con `get-pip.py`

### 5. El prompt define la calidad de las respuestas

```
# Demasiado restrictivo → responde "no encontré" aunque haya contexto
# Demasiado permisivo → el modelo inventa información

# Balance correcto:
Responde BASÁNDOTE en el contexto proporcionado.
Si hay información parcialmente relevante, úsala.
Solo si no hay absolutamente nada relacionado, indícalo.
NO inventes datos que no estén en el contexto.
```

---

## Caché semántico (desactivado por defecto)

El `RagService` incluye una implementación de caché semántico basada en 
similitud coseno entre embeddings de consultas, pero **está desactivado 
por defecto** (`SemanticCacheEnabled: false`).

### Por qué está desactivado

Pruebas empíricas con `nomic-embed-text` sobre texto administrativo en 
español muestran que no existe umbral coseno seguro que distinga 
paráfrasis genuinas de pares adversos (negaciones, cambios de entidad, 
cambios temporales):

- Similitud coseno máxima entre pares adversos: **0.9984**
- Similitud coseno mínima entre paráfrasis genuinas: **0.7470**

Cualquier umbral suficientemente alto para rechazar los pares adversos 
también rechaza las paráfrasis genuinas. Y como un hit del caché nunca 
llega al LLM, las respuestas incorrectas se sirven silenciosamente.

El experimento completo (metodología, 20 pares de prueba, tabla de 
resultados por categoría, discusión y decisión) está en 
[docs/experiments/threshold-safety.md](docs/experiments/threshold-safety.md).

### Cuándo se puede habilitar

Poner `"SemanticCacheEnabled": true` en `appsettings.json` **solo si** 
se ha verificado que la combinación específica de embedder + dominio 
no presenta el problema descrito arriba. Correr el script del 
experimento sobre corpus propio antes de decidir.

La lógica del caché (particionado por colección, modelo, prompt version 
y top-K) está en el código para quienes quieran auditarla o adaptarla, 
pero el default seguro es `false`.

### Crédito

El experimento que motivó esta decisión surgió del comentario de 
[Giulio D'Erme](https://dev.to/gde03/comment/3c9ni) en el hilo de 
dev.to del artículo original.

---

## 📊 Rendimiento en CPU (sin GPU)

Probado en servidor Windows con Intel Xeon:

| Recursos | Modelo | Tiempo respuesta |
|---------|--------|-----------------|
| 4 vCPU / 16GB RAM | Mistral 7B | 60-120 segundos |
| 16 vCPU / 32GB RAM | Mistral 7B | 20-45 segundos |
| 4 vCPU / 8GB RAM | phi3:mini | 15-30 segundos |
| GPU NVIDIA 8GB+ | Mistral 7B | 3-8 segundos |

---

## 🌍 Aplicabilidad

Aunque este ejemplo está orientado a documentos institucionales,
los patrones son universales:

✅ **Sector público** — normativas, circulares, lineamientos  
✅ **Legal** — contratos, jurisprudencia, regulaciones  
✅ **Salud** — protocolos, manuales clínicos  
✅ **Empresas** — políticas internas, manuales de procesos  
✅ **Educación** — reglamentos, programas de estudio  

Si alguna vez has pensado: *"Necesito IA pero no puedo enviar mis datos a la nube"* → este repositorio es para ti.

---

## 📚 Más información

Para arquitectura de sistemas de información en salud y patrones de diseño desde la trinchera:

**📖 [Arquitectura y diseño de sistemas integrales de gestión quirúrgica](https://www.amazon.com/-/es/Hubert-Garc%C3%ADa-Gordon-ebook/dp/B0GR8HBMXK/)**  
*Por Hubert García Gordon*  
ISBN: 978-9930-00-756-3

---

## 👤 Autor

**Hubert García Gordon**

- 10+ años en sistemas de información en salud
- Tutor UNED — Sistemas de Información en Salud
- LinkedIn: [hubert-garcia-24946925](https://www.linkedin.com/in/hubert-garcia-24946925/)

---

## 📄 Licencia

MIT License — ver archivo `LICENSE` para más detalles.

## 🤝 Contribuciones

¿Encontraste un problema? ¿Tienes una mejora?
Los pull requests son bienvenidos.

---

⭐ Si este repositorio te fue útil, considera darle una estrella y compartir el conocimiento.
