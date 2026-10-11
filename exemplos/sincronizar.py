"""Sincronização incremental de referência para a API de dados da Ziala.

Requer Python 3.9 ou superior, sem dependências externas.

Uso:
    export ZIALA_API_KEY=zk_live_...
    python sincronizar.py contacts

A cada execução:
1. lê a marca d'água da execução anterior em <stream>.estado.json;
2. pede GET /v1/<stream>?updated_since=<marca> e segue next_cursor até has_more = false;
3. repete 429, 500, 503 e falhas de rede, aguardando o Retry-After quando houver;
4. grava cada registro pela chave primária em <stream>.json (upsert);
5. só depois de gravar, salva o sync_watermark da última página como nova marca.
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


def chave_primaria(registro):
    """`id` em todos os objetos; `contact_id` + `field_key` em contact_fields."""
    if "id" in registro:
        return registro["id"]
    return f'{registro["contact_id"]}:{registro["field_key"]}'


def ler_json(caminho, padrao):
    if not os.path.exists(caminho):
        return padrao
    with open(caminho, encoding="utf-8") as f:
        return json.load(f)


def gravar_json(caminho, conteudo):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(conteudo, f, ensure_ascii=False, indent=2)


def pedir(url):
    """GET com novas tentativas em 429, 500, 503 e falha de rede."""
    for tentativa in range(MAX_TENTATIVAS):
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {CHAVE}"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as erro:
            if erro.code not in (429, 500, 503) or tentativa == MAX_TENTATIVAS - 1:
                raise
            espera = int(erro.headers.get("Retry-After") or 2 ** tentativa)
            motivo = f"HTTP {erro.code}"
        except urllib.error.URLError as erro:
            if tentativa == MAX_TENTATIVAS - 1:
                raise
            espera = 2 ** tentativa
            motivo = f"falha de rede ({erro.reason})"
        print(f"  {motivo}: aguardando {espera}s", file=sys.stderr)
        time.sleep(espera)


def sincronizar(stream):
    arq_dados = f"{stream}.json"
    arq_estado = f"{stream}.estado.json"
    registros = ler_json(arq_dados, {})
    marca = ler_json(arq_estado, {}).get("updated_since")

    params = {"limit": 200}
    if marca:
        params["updated_since"] = marca
    lidos = 0

    while True:
        pagina = pedir(f"{BASE}/{stream}?{urllib.parse.urlencode(params)}")
        for registro in pagina["data"]:
            registros[chave_primaria(registro)] = registro
            lidos += 1
        nova_marca = pagina["sync_watermark"]
        if not pagina["has_more"]:
            break
        params["cursor"] = pagina["next_cursor"]

    gravar_json(arq_dados, registros)
    gravar_json(arq_estado, {"updated_since": nova_marca})
    print(f"{stream}: {lidos} lidos, {len(registros)} no total, próxima marca {nova_marca}")


if __name__ == "__main__":
    if not CHAVE:
        sys.exit("Defina a variável de ambiente ZIALA_API_KEY.")
    sincronizar(sys.argv[1] if len(sys.argv) > 1 else "contacts")
