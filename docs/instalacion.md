# Guía de Instalación Paso a Paso

Este documento cubre, de principio a fin, la instalación de la
infraestructura en Windows Server sin Docker: Ollama, Qdrant y el ingestor
de Python. Los pasos 1 a 4 se completan tal como están escritos.

La parte .NET es distinta. El repositorio **no incluye un proyecto
ejecutable**: `dotnet/` son archivos de referencia para integrar en un
proyecto propio. El paso 5 dice qué tiene que aportar el lector.

---

## Requisitos mínimos

| Recurso | Mínimo | Recomendado |
|---------|--------|-------------|
| CPU | 4 vCPUs | 16 vCPUs |
| RAM | 16 GB | 32 GB |
| Disco | 20 GB libres | 50 GB libres |
| OS | Windows Server 2016+ | Windows Server 2022 |
| .NET | .NET 9 SDK | .NET 9 SDK |
| Python | 3.11+ | 3.11+ |

---

## Paso 1 — Instalar Ollama

1. Descargar desde https://ollama.com/download/windows
2. Ejecutar el instalador `.exe`
3. Descargar los modelos necesarios:

```powershell
ollama pull mistral
ollama pull nomic-embed-text
```

4. Verificar instalación:

```powershell
ollama list
```

### Configurar para aceptar conexiones externas

Por defecto Ollama **solo escucha en 127.0.0.1**. Si el ingestor Python
corre en otro servidor, configurar:

```powershell
$env:OLLAMA_HOST = "0.0.0.0:11434"
```

Para que persista al reiniciar, agregar como variable de entorno del sistema:

```powershell
[System.Environment]::SetEnvironmentVariable(
    "OLLAMA_HOST", "0.0.0.0:11434", "Machine")
```

### Registrar como Tarea Programada

```powershell
$action = New-ScheduledTaskAction `
    -Execute "C:\Users\USUARIO\AppData\Local\Programs\Ollama\ollama.exe" `
    -Argument "serve"

$trigger = New-ScheduledTaskTrigger -AtStartup

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit 0 -RestartCount 3

$principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask `
    -TaskName "Ollama" `
    -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal
```

> **El store de modelos depende del perfil bajo el que corra Ollama.**
> El `ollama pull` de más arriba guarda los modelos en
> `%USERPROFILE%\.ollama` del usuario que ejecutó el comando. La tarea de
> este ejemplo corre como `SYSTEM`, cuyo perfil es
> `C:\Windows\System32\config\systemprofile`, así que el servicio buscaría
> los modelos en una ruta distinta de la que los recibió. Los dos pasos
> pueden quedar bajo perfiles distintos, y conviene decidirlo antes de
> registrar la tarea y no después.

Dos formas de alinearlos, según convenga en el servidor:

- **Registrar la tarea con el mismo usuario que hizo el `ollama pull`**,
  en vez de `SYSTEM`. Cambiar `-UserId` en `New-ScheduledTaskPrincipal` y
  ajustar `-LogonType` al tipo de credencial que use ese usuario.
- **Fijar `OLLAMA_MODELS` a nivel máquina**, apuntando a una ruta que
  ambos perfiles puedan leer, y descargar los modelos con esa variable ya
  puesta:

```powershell
[System.Environment]::SetEnvironmentVariable(
    "OLLAMA_MODELS", "C:\Services\Ollama\models", "Machine")
```

### Verificar que el servicio ve los modelos

Después de registrar la tarea, arrancarla y consultar la lista de modelos:

```powershell
Start-ScheduledTask -TaskName "Ollama"
(Invoke-WebRequest http://localhost:11434/api/tags -UseBasicParsing).Content
```

La respuesta debe incluir los modelos del paso anterior. Si devuelve la
lista vacía (`{"models":[]}`), el servicio está corriendo pero leyendo un
store distinto al de la descarga: es la misma respuesta que daría un
Ollama sano al que todavía no le bajaron nada. Verificarlo acá convierte
lo que si no aparecería como un error en la primera consulta del RAG en
una comprobación de un solo comando.

---

## Paso 2 — Instalar Qdrant

1. Descargar desde https://github.com/qdrant/qdrant/releases
   - Buscar: `qdrant-x86_64-pc-windows-msvc.zip`

2. Extraer en `C:\Services\Qdrant\`

3. Probar que funciona:

```powershell
cd C:\Services\Qdrant
.\qdrant.exe
```

4. Verificar en PowerShell:

```powershell
Invoke-WebRequest http://localhost:6333 -UseBasicParsing | Select-Object StatusCode
# Debe mostrar: 200
```

5. Registrar como Tarea Programada:

```powershell
$action = New-ScheduledTaskAction `
    -Execute "C:\Services\Qdrant\qdrant.exe" `
    -WorkingDirectory "C:\Services\Qdrant"

$trigger = New-ScheduledTaskTrigger -AtStartup

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit 0 -RestartCount 3

$principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask `
    -TaskName "Qdrant" `
    -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal

Start-ScheduledTask -TaskName "Qdrant"
```

---

## Paso 3 — Instalar Python

### Opción A — Instalador normal (si no hay restricciones de GPO)

1. Descargar Python 3.11 desde https://python.org
2. Marcar obligatoriamente:
   - ✅ Add Python to PATH
   - ✅ Install for all users

### Opción B — Paquete embebible (para servidores con GPO restrictivas)

1. Descargar `python-3.11.x-amd64-embed.zip` desde https://python.org/downloads
2. Extraer en `C:\Python311\`
3. Editar `C:\Python311\python311._pth`:
   - Buscar la línea `#import site`
   - Cambiar a `import site` (quitar el `#`)
4. Descargar `get-pip.py` desde https://bootstrap.pypa.io/get-pip.py
5. Copiar a `C:\Python311\get-pip.py`
6. Ejecutar: `C:\Python311\python.exe C:\Python311\get-pip.py`

### Instalación offline (servidor sin internet)

En una PC con internet:
```powershell
pip download watchdog pdfplumber python-docx openpyxl qdrant-client ollama langchain-text-splitters `
    --python-version 311 --only-binary=:all: --platform win_amd64 `
    -d C:\paquetes_offline
```

Copiar `C:\paquetes_offline` al servidor y ejecutar:
```powershell
pip install --no-index --find-links C:\paquetes_offline `
    watchdog pdfplumber python-docx openpyxl qdrant-client ollama langchain-text-splitters
```

---

## Paso 4 — Configurar el ingestor

1. Copiar `python/config.example.json` como `python/config.json`
2. Editar `config.json`:

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

3. Probar manualmente:

```powershell
python python/ingestor.py
```

4. Registrar como Tarea Programada (igual que Qdrant, apuntando al `ingestor.py`).

---

## Paso 5 — Integrar en ASP.NET Core

> **El repositorio no trae un proyecto ejecutable.** No hay `.csproj`,
> `.sln` ni `Program.cs`. `dotnet/` son cinco archivos `.cs`
> —`IRagService.cs`, `RagController.cs`, `RagModels.cs`, `RagService.cs`
> y `RagSettings.cs`— pensados para integrarse en un proyecto ASP.NET Core
> que el lector aporta. A diferencia de los pasos anteriores, este no se
> completa solo con lo que hay en el repositorio.

Si todavía no existe un proyecto donde integrarlos, el mínimo es:

```powershell
dotnet new webapi -n MiApiRag
cd MiApiRag
```

Después:

1. Copiar los archivos de `dotnet/` a su proyecto
2. Registrar en `Program.cs`:

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

3. Agregar en `appsettings.json`:

```json
"RagSettings": {
  "QdrantUrl": "http://localhost:6333",
  "OllamaUrl": "http://localhost:11434",
  "CollectionName": "mis-documentos",
  "EmbeddingModel": "nomic-embed-text",
  "ChatModel": "mistral",
  "MaxResults": 5,
  "SemanticCacheEnabled": false
}
```

`SemanticCacheEnabled` viene en `false` a propósito. El caché semántico
sirve una respuesta cacheada sin pasar por el LLM, y no existe umbral
coseno que distinga paráfrasis genuinas de negaciones o cambios de
entidad con `nomic-embed-text` sobre texto administrativo en español.
No lo pongas en `true` sin correr el experimento sobre tu propio corpus:
[docs/experiments/threshold-safety.md](experiments/threshold-safety.md).

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

4. Probar el endpoint. El controlador expone `POST /Rag/query` y espera un
   cuerpo JSON con `question`. El campo `collection` es opcional: si se
   omite, usa el `CollectionName` de la configuración.

```powershell
$body = @{ question = "¿Cuál es el procedimiento para solicitar un permiso?" } |
    ConvertTo-Json

# El cuerpo va como bytes UTF-8: con acentos y signos de apertura, pasar
# la cadena directamente los corrompe en Windows PowerShell 5.1.
Invoke-RestMethod -Method Post `
    -Uri http://localhost:5000/Rag/query `
    -ContentType "application/json; charset=utf-8" `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

Reemplazar el puerto por el que imprima `dotnet run` al arrancar. La
respuesta trae `answer` y `sources`, y cada fuente trae `filename`, `text`
y `score`.

Swagger no está disponible sin configurarlo: no lo trae el repositorio ni
la plantilla `webapi` de .NET 9. Si se lo quiere, hay que agregarlo aparte.

---

## Verificación final

```powershell
# Qdrant funcionando
Invoke-WebRequest http://localhost:6333 -UseBasicParsing | Select-Object StatusCode

# Ollama funcionando y escuchando en todas las interfaces
netstat -ano | findstr :11434

# Colección creada con documentos indexados
Invoke-WebRequest http://localhost:6333/collections/mis-documentos -UseBasicParsing
```
