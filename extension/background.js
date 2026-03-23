const HOST_NAME = "com.leo.detector_duplicados";

// NUEVO EVENTO: onDeterminingFilename intercepta ANTES de la ventana "Guardar como"
chrome.downloads.onDeterminingFilename.addListener((downloadItem, suggest) => {
    console.log("Evaluando nombre para:", downloadItem.filename);

    // 1. Abrimos conexión con Python
    let port = chrome.runtime.connectNative(HOST_NAME);

    // 2. Extraemos el nombre limpio
    let nombreArchivo = downloadItem.filename;
    if (!nombreArchivo) {
        nombreArchivo = downloadItem.url.split('?')[0].split('/').pop();
    } else {
        nombreArchivo = nombreArchivo.split('\\').pop().split('/').pop();
    }
    nombreArchivo = decodeURIComponent(nombreArchivo);
    
    console.log("Nombre a buscar:", nombreArchivo);

    // 3. Le mandamos el mensaje a Python
    port.postMessage({ archivo: nombreArchivo });

    // 4. ESCUCHAMOS LA RESPUESTA
    port.onMessage.addListener((respuesta) => {
        console.log("Respuesta recibida desde Python:", respuesta);

        if (respuesta.encontrado) {
            console.log(`🛑 ¡El archivo ya existe! Cancelando descarga...`);
            
            // Cancelamos la descarga ANTES de que salga la ventana
            chrome.downloads.cancel(downloadItem.id);
            
            // Lanzamos la notificación nativa chiquita
            chrome.notifications.create({
                type: "basic",
                iconUrl: "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
                title: "Descarga cancelada",
                message: "El archivo ya existe. Abriendo la carpeta...",
                priority: 2
            });

            // Liberamos el evento de Chrome sin sugerir nombre
            suggest();
            
        } else {
            console.log("✅ Archivo nuevo. Permitiendo ventana de guardado...");
            // Si el archivo NO existe, le decimos a Chrome que siga su curso normal
            suggest({ filename: downloadItem.filename });
        }
        
        // Cerramos el puerto
        port.disconnect();
    });

    // 5. Manejo de errores
    port.onDisconnect.addListener(() => {
        if (chrome.runtime.lastError) {
            console.error("Error de conexión:", chrome.runtime.lastError.message);
            // Si Python falla, dejamos que descargue normal
            suggest({ filename: downloadItem.filename });
        }
    });

    // IMPORTANTE: Retornamos 'true' para decirle a Chrome que la respuesta 
    // va a llegar de forma asíncrona (después de que Python busque en el disco)
    return true;
});