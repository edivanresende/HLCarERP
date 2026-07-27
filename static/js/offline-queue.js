/**
 * HLCarERP - Fila de ações offline
 */
function gerarUUID() {
    if (crypto && crypto.randomUUID) return crypto.randomUUID();
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

async function enfileirarAcao(metodo, url, body = null, tipo = 'Ação') {
    const acao = {
        uuid: gerarUUID(),
        metodo: metodo.toUpperCase(),
        url: url,
        body: body,
        tipo: tipo,
        criado_em: new Date().toISOString(),
        tentativas: 0,
        status: 'pendente'
    };
    await window.HLOfflineDB.salvarItem(window.HLOfflineDB.STORES.fila, acao);
    console.log('[HL Offline] Ação enfileirada:', acao.tipo);
    if (window.atualizarIndicadorOffline) window.atualizarIndicadorOffline();
    return acao;
}

async function listarFila() {
    return await window.HLOfflineDB.listar(window.HLOfflineDB.STORES.fila);
}

async function removerDaFila(uuid) {
    return await window.HLOfflineDB.removerItem(window.HLOfflineDB.STORES.fila, uuid);
}

async function atualizarAcao(acao) {
    return await window.HLOfflineDB.salvarItem(window.HLOfflineDB.STORES.fila, acao);
}

async function processarFila() {
    if (!navigator.onLine) return 0;
    const fila = await listarFila();
    if (fila.length === 0) return 0;

    console.log(`[HL Offline] Processando ${fila.length} ação(ões)...`);
    let sucesso = 0;
    fila.sort((a, b) => new Date(a.criado_em) - new Date(b.criado_em));

    for (const acao of fila) {
        try {
            acao.status = 'enviando';
            acao.tentativas = (acao.tentativas || 0) + 1;
            await atualizarAcao(acao);

            const options = {
                method: acao.metodo,
                headers: { 'Content-Type': 'application/json', 'X-Offline-Sync': '1' }
            };
            if (acao.body && ['POST', 'PUT', 'PATCH'].includes(acao.metodo)) {
                options.body = JSON.stringify(acao.body);
            }

            const response = await fetch(acao.url, options);
            if (response.ok || response.status === 302) {
                await removerDaFila(acao.uuid);
                sucesso++;
            } else {
                acao.status = 'erro';
                acao.ultimo_erro = `HTTP ${response.status}`;
                await atualizarAcao(acao);
            }
        } catch (err) {
            acao.status = 'erro';
            acao.ultimo_erro = err.message;
            await atualizarAcao(acao);
        }
    }
    if (window.atualizarIndicadorOffline) window.atualizarIndicadorOffline();
    return sucesso;
}

window.HLOfflineQueue = { enfileirarAcao, listarFila, removerDaFila, processarFila };