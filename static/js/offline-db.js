/**
 * HLCarERP - Camada de armazenamento offline (IndexedDB)
 */
const DB_NAME = 'HLCarERP_Offline';
const DB_VERSION = 1;

const STORES = {
    clientes: 'clientes',
    veiculos: 'veiculos',
    produtos: 'produtos',
    ordens: 'ordens',
    fila: 'fila_sync',
    meta: 'meta'
};

function openDB() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);
        request.onerror = () => reject(request.error);
        request.onsuccess = () => resolve(request.result);
        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            if (!db.objectStoreNames.contains(STORES.clientes)) {
                const store = db.createObjectStore(STORES.clientes, { keyPath: 'id' });
                store.createIndex('nome', 'nome', { unique: false });
            }
            if (!db.objectStoreNames.contains(STORES.veiculos)) {
                const store = db.createObjectStore(STORES.veiculos, { keyPath: 'id' });
                store.createIndex('placa', 'placa', { unique: false });
                store.createIndex('cliente_id', 'cliente_id', { unique: false });
            }
            if (!db.objectStoreNames.contains(STORES.produtos)) {
                const store = db.createObjectStore(STORES.produtos, { keyPath: 'id' });
                store.createIndex('codigo', 'codigo', { unique: false });
            }
            if (!db.objectStoreNames.contains(STORES.ordens)) {
                const store = db.createObjectStore(STORES.ordens, { keyPath: 'id' });
                store.createIndex('status', 'status', { unique: false });
            }
            if (!db.objectStoreNames.contains(STORES.fila)) {
                const store = db.createObjectStore(STORES.fila, { keyPath: 'uuid' });
                store.createIndex('criado_em', 'criado_em', { unique: false });
            }
            if (!db.objectStoreNames.contains(STORES.meta)) {
                db.createObjectStore(STORES.meta, { keyPath: 'chave' });
            }
        };
    });
}

async function getStore(storeName, mode = 'readonly') {
    const db = await openDB();
    return db.transaction(storeName, mode).objectStore(storeName);
}

async function salvarLista(storeName, lista) {
    const db = await openDB();
    const tx = db.transaction(storeName, 'readwrite');
    const store = tx.objectStore(storeName);
    await new Promise((resolve, reject) => {
        const clearReq = store.clear();
        clearReq.onsuccess = resolve;
        clearReq.onerror = () => reject(clearReq.error);
    });
    for (const item of lista) { store.put(item); }
    return new Promise((resolve, reject) => {
        tx.oncomplete = () => resolve(true);
        tx.onerror = () => reject(tx.error);
    });
}

async function listar(storeName) {
    const store = await getStore(storeName);
    return new Promise((resolve, reject) => {
        const req = store.getAll();
        req.onsuccess = () => resolve(req.result || []);
        req.onerror = () => reject(req.error);
    });
}

async function buscarPorId(storeName, id) {
    const store = await getStore(storeName);
    return new Promise((resolve, reject) => {
        const req = store.get(id);
        req.onsuccess = () => resolve(req.result || null);
        req.onerror = () => reject(req.error);
    });
}

async function salvarItem(storeName, item) {
    const store = await getStore(storeName, 'readwrite');
    return new Promise((resolve, reject) => {
        const req = store.put(item);
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => reject(req.error);
    });
}

async function removerItem(storeName, id) {
    const store = await getStore(storeName, 'readwrite');
    return new Promise((resolve, reject) => {
        const req = store.delete(id);
        req.onsuccess = () => resolve(true);
        req.onerror = () => reject(req.error);
    });
}

async function setMeta(chave, valor) {
    const store = await getStore(STORES.meta, 'readwrite');
    return new Promise((resolve, reject) => {
        const req = store.put({ chave, valor, atualizado_em: new Date().toISOString() });
        req.onsuccess = () => resolve(true);
        req.onerror = () => reject(req.error);
    });
}

async function getMeta(chave) {
    const store = await getStore(STORES.meta);
    return new Promise((resolve, reject) => {
        const req = store.get(chave);
        req.onsuccess = () => resolve(req.result ? req.result.valor : null);
        req.onerror = () => reject(req.error);
    });
}

window.HLOfflineDB = {
    STORES, openDB, salvarLista, listar, buscarPorId, salvarItem, removerItem, setMeta, getMeta
};