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
│   ├── arquitectura.md      # Decisiones de diseño
│   └── problemas-comunes.md # Troubleshooting
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
builder.Services.AddHttpClient("ollama");
builder.Services.AddScoped<IRagService, RagService>();
```

Agregar en `appsettings.json`:

```json
"RagSettings": {
  "QdrantUrl": "http://localhost:6333",
  "OllamaUrl": "http://localhost:11434",
  "CollectionName": "mis-documentos",
  "EmbeddingModel": "nomic-embed-text",
  "ChatModel": "mistral",
  "MaxResults": 5
}
```

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

```csharp
// ❌ Default 100s — Mistral en CPU tarda 60-120s
var client = new HttpClient();

// ✅ Configurar explícitamente
var client = new HttpClient { Timeout = TimeSpan.FromSeconds(300) };
```

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

## 🚀 Caché semántico

Para mejorar el tiempo de respuesta, el `RagService` incluye
caché semántico usando similitud coseno:

- **Umbral:** 0.92 (preguntas muy similares usan la respuesta cacheada)
- **TTL:** 24 horas
- **Máximo:** 200 entradas
- **Thread-safe:** SemaphoreSlim

```
Primera consulta:  ~90 segundos (Mistral en CPU)
Segunda consulta similar: < 1 segundo (desde caché)
```

⚠️ **Importante:** limpiar el caché al cambiar de modelo LLM.

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
