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

## Qdrant SDK falla con errores gRPC

**Síntoma:** `Grpc.Core.RpcException: Status(StatusCode="Internal")` al usar el SDK de Qdrant para .NET.

**Causa:** El SDK oficial usa gRPC por defecto. Qdrant en modo estándar usa HTTP/1.1 REST.

**Solución:** No usar el SDK. Usar HttpClient REST directamente:

```csharp
// ❌ NO usar el SDK
// var client = new QdrantClient(new Uri(url));

// ✅ HttpClient REST directo
var response = await _httpClient.PostAsync(
    $"{qdrantUrl}/collections/{collection}/points/search",
    content);
```

---

## HttpClient timeout al consultar Mistral

**Síntoma:** `TaskCanceledException: The request was canceled due to the configured HttpClient.Timeout of 100 seconds`

**Causa:** Mistral en CPU tarda 60-120 segundos. El timeout por defecto de HttpClient es 100 segundos.

**Solución:**
```csharp
// ✅ Configurar timeout explícitamente
using var client = new HttpClient
{
    Timeout = TimeSpan.FromSeconds(300)
};
```

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

## El caché devuelve respuestas incorrectas al cambiar de modelo

**Síntoma:** Después de cambiar `ChatModel` en `appsettings.json`, las respuestas siguen siendo las del modelo anterior.

**Causa:** El caché semántico es en memoria y no sabe que cambió el modelo LLM.

**Solución:** Llamar al endpoint de limpieza de caché:
```
DELETE /Rag/cache/clear
```

O reiniciar el servicio API.

---

## El browser no puede conectar con la API interna

**Síntoma:** `ERR_CONNECTION_TIMED_OUT` o `ERR_CONNECTION_REFUSED` en el browser al hacer fetch a una IP interna.

**Causa:** El browser del usuario no tiene ruta de red al datacenter interno.

**Solución:** Implementar un handler proxy server-side (`.ashx` en WebForms o endpoint en MVC) que reciba la petición del browser y la reenvíe internamente:

```
Browser → /ChatHandler (servidor web) → API interna → Ollama
```

Ver ejemplo en `dotnet/RagController.cs`.

---

## Las respuestas son "No encontré información" aunque los documentos existan

**Síntomas:** El modelo responde que no encontró información aunque las fuentes muestren chunks relevantes.

**Causas posibles:**

1. **Prompt demasiado restrictivo** — Ajustar el prompt en `RagService.cs` para ser menos estricto.

2. **Caché con respuesta incorrecta** — Limpiar con `DELETE /Rag/cache/clear`.

3. **Modelo muy pequeño** — Modelos de 1-3B parámetros tienen dificultad con español y documentos técnicos. Usar `mistral` (7B) para mejor calidad.

4. **Contexto insuficiente** — Aumentar `MaxResults` de 5 a 8 en `appsettings.json`.

---

## net use genera alertas de seguridad

**Síntoma:** El equipo de seguridad (SOC) alerta sobre ejecución de `net use` con credenciales.

**Causa:** `net use` transmite credenciales en texto plano y es detectado como potencial exfiltración.

**Solución:** Configurar la Tarea Programada del ingestor para correr con el usuario de dominio que ya tiene acceso al recurso de red. Windows maneja la autenticación transparentemente sin necesidad de `net use`.
