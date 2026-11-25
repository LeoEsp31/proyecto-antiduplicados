const HOST_NAME = "com.leo.detector_duplicados";

// Si Python no responde en este tiempo, la descarga sigue normal.
// (Python corta su búsqueda a los 8 s; esto es un respaldo por si se cuelga.)
const ESPERA_MAXIMA_MS = 12000;

function nombreDelArchivo(item) {
    let nombre = item.filename || (item.url || "").split("?")[0].split("#")[0].split("/").pop();
    nombre = (nombre || "").split("\\").pop().split("/").pop();
    try {
        nombre = decodeURIComponent(nombre);
    } catch {
        // Si tiene un '%' suelto, usamos el nombre tal como vino.
    }
    return nombre.trim();
}

function avisar(titulo, mensaje) {
    chrome.notifications.create({
        type: "basic",
        iconUrl: "icono.png",
        title: titulo,
        message: mensaje,
        priority: 2
    });
}

// onDeterminingFilename intercepta la descarga ANTES de la ventana "Guardar como".
chrome.downloads.onDeterminingFilename.addListener((downloadItem, suggest) => {
    const nombreArchivo = nombreDelArchivo(downloadItem);
    if (!nombreArchivo) {
        return; // Sin nombre no hay nada que buscar: Chrome sigue solo.
    }
    console.log("Nombre a buscar:", nombreArchivo);

    let port;
    try {
        port = chrome.runtime.connectNative(HOST_NAME);
    } catch (error) {
        console.error("No se pudo conectar con Python:", error);
        return;
    }

    // suggest() se puede llamar una sola vez: este candado evita llamarlo dos veces
    // si llegan la respuesta, el corte de conexión y el tiempo límite a la vez.
    let resuelto = false;
    const terminar = () => {
        if (resuelto) return;
        resuelto = true;
        clearTimeout(temporizador);
        suggest(); // sin argumentos: Chrome usa el nombre que ya tenía
        try { port.disconnect(); } catch { /* ya estaba cerrado */ }
    };

    const temporizador = setTimeout(() => {
        console.warn("Python tardó demasiado. Se permite la descarga.");
        terminar();
    }, ESPERA_MAXIMA_MS);

    port.onMessage.addListener((respuesta) => {
        console.log("Respuesta de Python:", respuesta);
        if (resuelto) return;

        if (respuesta.encontrado) {
            chrome.downloads.cancel(downloadItem.id);
            const carpeta = respuesta.ruta.slice(0, respuesta.ruta.lastIndexOf("\\"));
            avisar(
                "Descarga cancelada: ya tenés este archivo",
                respuesta.carpeta_ya_abierta
                    ? `Está en ${carpeta} (esa carpeta ya está abierta).`
                    : `Está en ${carpeta}. Abriendo la carpeta...`
            );
        } else if (respuesta.tiempo_agotado) {
            console.warn("La búsqueda se cortó por tiempo. Se permite la descarga.");
        }
        terminar();
    });

    port.onDisconnect.addListener(() => {
        if (chrome.runtime.lastError) {
            console.error("Error de conexión:", chrome.runtime.lastError.message);
        }
        terminar(); // Si Python se cerró sin responder, la descarga sigue normal.
    });

    port.postMessage({ archivo: nombreArchivo });

    // true = la respuesta llega después (cuando Python termine de buscar).
    return true;
});
