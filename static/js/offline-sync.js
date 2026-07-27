/**
 * HLCarERP - Sincronização e detecção online/offline
 */
const SYNC_ENDPOINTS = {
    clientes: '/api/offline/clientes',
    veiculos: '/api/offline/veiculos',
    produtos: '/api/offline/produtos',
    ordens: '/api/offline/ordens'
};

async function baixarDadosDoServidor() {
    if (!navigator.onLine) return false;
    try {
        for (const [nome, url] of Object.entries(SYNC_ENDPOINTS)) {
            const r = await fetch(url);
            if (r.ok) {
                const data = await r.json();
                await window.HLOfflineDB.salvarLista(window.HLOfflineDB.STORES[nome], data);
                console.log(`[HL Sync] ${nome} atualizados:`, data.length);
            }
        }
        await window.HLOfflineDB.setMeta('ultima_sync', new Date().toISOString());
        return true;
    } catch (err) {
        console.error('[HL Sync] Erro:', err);
        return false;
    }
}

async function sincronizarTudo() {
    if (!navigator.onLine) return { enviados: 0, baixados: false };
    const enviados = await window.HLOfflineQueue.processarFila();
    const baixados = await baixarDadosDoServidor();
    return { enviados, baixados };
}

async function atualizarIndicadorOffline() {
    const badge = document.getElementById('hl-offline-badge');
    if (!badge) return;
    const online = navigator.onLine;
    let pendentes = 0;
    try {
        const fila = await window.HLOfflineQueue.listarFila();
        pendentes = fila.length;
    } catch (e) {}

    if (!online) {
        badge.className = 'hl-badge offline';
        badge.innerHTML = '<i class="fa fa-wifi"></i> Offline' + (pendentes > 0 ? ` (${pendentes})` : '');
        badge.title = 'Sem internet. As alterações serão enviadas quando voltar.';
    } else if (pendentes > 0) {
        badge.className = 'hl-badge syncing';
        badge.innerHTML = `<i class="fa fa-sync fa-spin"></i> Sincronizando (${pendentes})`;
    } else {
        badge.className = 'hl-badge online';
        badge.innerHTML = '<i class="fa fa-check-circle"></i> Online';
    }
}
window.atualizarIndicadorOffline = atualizarIndicadorOffline;

function iniciarModoHibrido() {
    window.addEventListener('online', async () => {
        atualizarIndicadorOffline();
        await sincronizarTudo();
        atualizarIndicadorOffline();
    });
    window.addEventListener('offline', () => atualizarIndicadorOffline());
    atualizarIndicadorOffline();
    if (navigator.onLine) {
        setTimeout(async () => {
            await sincronizarTudo();
            atualizarIndicadorOffline();
        }, 1500);
    }
    setInterval(async () => {
        if (navigator.onLine) {
            await sincronizarTudo();
            atualizarIndicadorOffline();
        }
    }, 120000);
}

window.HLOfflineSync = { baixarDadosDoServidor, sincronizarTudo, atualizarIndicadorOffline, iniciarModoHibrido };

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', iniciarModoHibrido);
} else {
    iniciarModoHibrido();
}