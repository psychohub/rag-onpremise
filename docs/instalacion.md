# Guía de Instalación Paso a Paso

Este documento cubre la instalación completa en Windows Server sin Docker.

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

1. Copiar los archivos de `dotnet/` a su proyecto
2. Registrar en `Program.cs`:

```csharp
builder.Services.Configure<RagSettings>(
    builder.Configuration.GetSection("RagSettings"));
builder.Services.AddHttpClient();
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
  "MaxResults": 5
}
```

4. Probar en Swagger:

```
POST /Rag/query
{
  "question": "¿Cuál es el procedimiento para solicitar un permiso?"
}
```

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
