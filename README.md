# Documentação da API de dados da Ziala

Fonte do site de documentação pública da API de dados (Mintlify). Todo push na
`main` publica o site automaticamente.

- Páginas: arquivos `.mdx` na raiz e em `guias/`.
- Menu, cores e logo: `docs.json`.
- Referência dos endpoints: gerada do contrato público em
  `https://api.ziala.com.br/v1/openapi.json`, servido pela própria API.

## Ver localmente

```
npx mint dev
```

Abre em `http://localhost:3000`.

## Regras

- Este repositório é público. Nunca coloque aqui chave, token, dado de cliente ou
  trecho do código do produto.
- Texto que o cliente lê: português do Brasil, acentuado, sem travessão longo.
- Exemplos com dados inventados.
