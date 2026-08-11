# Problemas Comunes y Soluciones

---

## Ollama no acepta conexiones desde otros servidores

**Síntoma:** `Connection refused` o `Connection timed out` al puerto 11434 desde otro servidor.

**Causa:** Ollama por defecto solo escucha en `127.0.0.1`.

**Solución:**
```powershell
# Verificar en qué interfaz escucha
netstat -ano | findstr :11434
# Si muestra 127.0.0.1 → solo acepta conexiones locales

# Reiniciar con variable de entorno
Get-Process ollama | Stop-Process -Force
$env:OLLAMA_HOST = "0.0.0.0:11434"
Start-Process "ollama.exe" -ArgumentList "serve" -WindowStyle Hidden

# Verificar que ahora escucha en todas las interfaces
netstat -ano | findstr :11434
# Debe mostrar: 0.0.0.0:11434
```

---

## El SDK de Qdrant para .NET falla con errores gRPC

**Síntoma:** `Grpc.Core.RpcException: Status(StatusCode="Internal")` al usar el SDK de Qdrant para .NET.

**Causa:** El SDK de .NET habla gRPC por defecto y falla detrás de proxies o balanceadores HTTP/1.1. Qdrant expone REST en el puerto 6333 y gRPC en el 6334.

**Solución:** En .NET, no usar el SDK. Hablar REST con un cliente nombrado de `IHttpClientFactory`, que es lo que hace `RagService`:

```csharp
// ❌ El SDK de .NET usa gRPC
// var client = new QdrantClient(new Uri(url));

// ✅ REST directo, con el cliente nombrado "qdrant"
var client = _httpClientFactory.CreateClient("qdrant");
var response = await client.PostAsync(
    $"{_settings.QdrantUrl}/collections/{collection}/points/search",
    content, cancellationToken);
```

**Esto no aplica al SDK de Python.** El ingestor usa `qdrant-client`, declarado en `python/requirements.txt`, y lo construye como `QdrantClient(url=cfg["qdrant_url"])` en `python/ingestor.py`. Sin `prefer_grpc=True` el cliente de Python sale por REST contra el 6333, que es el puerto de `qdrant_url` en la configuración de ejemplo. Ahí el SDK oficial es la forma recomendada y no presenta este problema.

---

## HttpClient timeout al consultar Mistral

**Síntoma:** `TaskCanceledException: The request was canceled due to the configured HttpClient.Timeout of 100 seconds`

**Causa:** Mistral en CPU tarda 60-120 segundos. El timeout por defecto de HttpClient es 100 segundos.

**Solución:** `RagService` no construye `HttpClient`: pide clientes
nombrados a `IHttpClientFactory` en sus cuatro llamadas. El timeout se
configura al registrarlos, en el `Program.cs` de su proyecto:

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

Si el síntoma persiste, revisar que los tres nombres del registro
coincidan exactamente con los de `CreateClient(...)`: un nombre sin
registrar no falla al arrancar, devuelve un cliente con el default de
100 segundos y la generación vuelve a morir en el mismo punto.

---

## Python MSI no instala en Windows Server

**Síntoma:** `Error 0x80070643: Failed to install MSI package` durante la instalación de Python.

**Causa:** Restricciones de GPO corporativas bloquean instaladores MSI para usuarios no administradores.

**Solución:** Usar el paquete embebible de Python (ver [instalacion.md](instalacion.md) — Opción B).

---

## pip no funciona en Python embebible

**Síntoma:** `ModuleNotFoundError: No module named 'pip'` después de instalar pip.

**Causa:** El paquete embebible tiene deshabilitado el sistema de sitios por defecto.

**Solución:**
1. Abrir `C:\Python311\python311._pth` con Notepad
2. Buscar la línea `#import site`
3. Cambiarla a `import site` (quitar el `#`)
4. Guardar y reintentar

---

## El caché sigue sirviendo respuestas viejas

**Síntoma:** Con `SemanticCacheEnabled` en `true`, una consulta devuelve una respuesta que ya no corresponde a los documentos indexados.

**Lo que ya no es causa:** cambiar `ChatModel`, `EmbeddingModel`, `MaxResults` o la colección. La clave del caché (`BuildCacheKey` en `RagService.cs`) incluye colección, modelo de embeddings, modelo de chat, versión de prompt y top-K. Cambiar cualquiera de esos manda las consultas nuevas a otra partición y deja las entradas viejas inalcanzables por sí solas: no hace falta limpieza manual.

**Lo que sí queda descubierto:**

1. **El estado del corpus.** Reingestar, agregar o retirar documentos no cambia la clave, porque no existe contador de revisión del corpus. Está registrado como diseño pendiente en [ADR-001](adr/001-cache-partitioning-by-authorization-scope.md).

2. **Editar el template del prompt sin subir `PROMPT_VERSION`.** Esa constante se incrementa a mano en `RagService.cs`; si no se toca, las respuestas viejas siguen en la misma partición.

**Solución para esos dos casos:**
```
DELETE /Rag/cache/clear
```

O reiniciar el servicio: el caché es en memoria y no sobrevive al reinicio.

Con la configuración que entrega el repositorio (`SemanticCacheEnabled: false`) este problema no puede ocurrir.

---

## El browser no puede conectar con la API interna

**Síntoma:** `ERR_CONNECTION_TIMED_OUT` o `ERR_CONNECTION_REFUSED` en el browser al hacer fetch a una IP interna.

**Causa:** El browser del usuario no tiene ruta de red al datacenter interno.

**Solución:** Implementar un handler proxy server-side (`.ashx` en WebForms o endpoint en MVC) que reciba la petición del browser y la reenvíe internamente:

```
Browser → /ChatHandler (servidor web) → API interna → Ollama
```

> **Patrón sugerido, no implementado.** El repositorio no trae ese handler.
> `dotnet/RagController.cs` expone la API RAG —`query`, `test`,
> `cache/stats`, `cache/clear`— y no reenvía peticiones de terceros. El
> diagrama describe la forma de la solución, no código de este repo.

---

## Las respuestas son "No encontré información" aunque los documentos existan

**Síntomas:** El modelo responde que no encontró información aunque las fuentes muestren chunks relevantes.

**Causas posibles:**

1. **Prompt demasiado restrictivo** — Ajustar el prompt en `RagService.cs` para ser menos estricto.

2. **Caché con respuesta incorrecta** — Solo aplica si `SemanticCacheEnabled` está en `true`; con el default (`false`) el caché no participa. Limpiar con `DELETE /Rag/cache/clear`.

3. **Modelo muy pequeño** — Modelos de 1-3B parámetros tienen dificultad con español y documentos técnicos. Usar `mistral` (7B) para mejor calidad.

4. **Contexto insuficiente** — Aumentar `MaxResults` de 5 a 8 en `appsettings.json`.

---

## net use genera alertas de seguridad

**Síntoma:** El equipo de seguridad (SOC) alerta sobre ejecución de `net use` con credenciales.

**Causa:** `net use` transmite credenciales en texto plano y es detectado como potencial exfiltración.

**Solución:** Configurar la Tarea Programada del ingestor para correr con el usuario de dominio que ya tiene acceso al recurso de red. Windows maneja la autenticación transparentemente sin necesidad de `net use`.
