"""Exemplo de referência da API de dados da Ziala: sincroniza um stream para um arquivo local.

Só biblioteca padrão do Python 3.9+. Uso:

    ZIALA_API_KEY=zk_live_... python sincronizar.py contacts

A cada execução:
1. lê do arquivo de estado a marca d'água da execução anterior (ou começa do zero);
2. pede `GET /v1/<stream>?updated_since=<esse valor>` e segue `next_cursor` até
   `has_more` ser falso;
3. respeita `Retry-After` quando recebe 429 ou 503;
4. grava cada linha pela chave primária (`id`): a mesma linha lida duas vezes na borda
   de uma página substitui a anterior, nunca duplica;
5. só então salva no estado o `sync_watermark` da última página: o instante até onde a
   API garante que a resposta está completa.

A entrega é "pelo menos uma vez": a API lê a partir de `updated_since` (maior OU IGUAL,
com alguns minutos de recuo), então linhas da borda podem vir repetidas. É esperado, e o
passo 4 resolve. Guardar a marca d'água da API, e não o relógio local nem o maior
`updated_at` lido, é o que garante que nada se perde.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("ZIALA_API_URL", "https://api.ziala.com.br/v1")
CHAVE = os.environ.get("ZIALA_API_KEY")
MAX_TENTATIVAS = 5


def pedir(url):
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {CHAVE}"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as erro:
            if erro.code in (429, 503) and tentativa < MAX_TENTATIVAS:
                espera = int(erro.headers.get("Retry-After") or 2 ** tentativa)
                print(f"  {erro.code}: aguardando {espera}s", file=sys.stderr)
                time.sleep(espera)
                continue
            raise


def sincronizar(stream):
    arq_dados = f"{stream}.json"
    arq_estado = f"{stream}.estado.json"
    linhas = json.load(open(arq_dados, encoding="utf-8")) if os.path.exists(arq_dados) else {}
    estado = json.load(open(arq_estado, encoding="utf-8")) if os.path.exists(arq_estado) else {}

    params = {"limit": 200}
    if estado.get("updated_since"):
        params["updated_since"] = estado["updated_since"]
    marca = estado.get("updated_since")
    lidas = 0

    while True:
        pagina = pedir(f"{BASE}/{stream}?{urllib.parse.urlencode(params)}")
        for linha in pagina["data"]:
            linhas[linha["id"]] = linha
            lidas += 1
        marca = pagina["sync_watermark"]
        if not pagina["has_more"]:
            break
        params["cursor"] = pagina["next_cursor"]

    with open(arq_dados, "w", encoding="utf-8") as f:
        json.dump(linhas, f, ensure_ascii=False, indent=2)
    with open(arq_estado, "w", encoding="utf-8") as f:
        json.dump({"updated_since": marca}, f)
    print(f"{stream}: {lidas} linhas lidas, {len(linhas)} no total, próximo corte {marca}")


if __name__ == "__main__":
    if not CHAVE:
        sys.exit("Defina ZIALA_API_KEY.")
    sincronizar(sys.argv[1] if len(sys.argv) > 1 else "contacts")
