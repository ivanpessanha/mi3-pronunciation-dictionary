# Formato do dicionário

Contrato entre este repositório, a interface de alimentação e o app. **Versão do
formato: 1.**

## Visão geral

| Arquivo | Quem escreve | Para quê |
|---|---|---|
| `dictionaries/<locale>/lexicon.tsv` | interface de alimentação | fonte da verdade, em texto |
| `manifest.json` | fluxo de publicação | o que o app consulta a cada abertura |
| `lexicon-<locale>-r<N>.tsv.gz` (na Release) | fluxo de publicação | o que o app baixa |

Um commit em `lexicon.tsv` **não chega aos usuários**. Só a publicação gera uma nova
revisão e, com ela, a pergunta no app. Assim, várias edições viram uma só atualização.

## `lexicon.tsv`

UTF-8 sem BOM, fim de linha LF e uma quebra de linha no fim do arquivo.

```text
#format=1
#locale=pt-BR
gpu<TAB>s<TAB>pt<TAB>curated<TAB>h<TAB>m<TAB><TAB><TAB>Gê-Pê-U<TAB><TAB>
```

### Cabeçalho

| Linha | Significado |
|---|---|
| `#format=1` | versão do layout das linhas |
| `#locale=pt-BR` | idioma **da voz que lê** (BCP 47); deve ser igual ao nome da pasta |

A publicação acrescenta `#revision=N` e `#version=<locale>-rN` ao arquivo distribuído.
Não escreva essas duas linhas em `lexicon.tsv`.

### Colunas

São sempre 11, separadas por TAB, mesmo quando vazias.

| # | Coluna | Obrigatória | Valores |
|---|---|---|---|
| 1 | `key` | sim | termo normalizado: minúsculas, sem espaços nas pontas, `'` reto. Expressões usam um espaço entre as palavras |
| 2 | `kind` | sim | `n` nome, `t` termo, `s` sigla |
| 3 | `lang` | não | idioma **de origem** do termo: `en`, `fr`, `pt`… |
| 4 | `source` | sim | origem: `curated`, `cmudict`, `wikidata`, `deny`, `ptword` ou outra, como o nome da interface |
| 5 | `ref` | sim | confiança na pronúncia de referência: `h`, `m`, `l` |
| 6 | `approx` | sim | confiança na grafia para a voz: `h`, `m`, `l` |
| 7 | `flags` | não | `a` aprovado por revisão humana, `x` ambíguo. Podem vir juntos |
| 8 | `ipa` | não | pronúncia em IPA; alternativas separadas por `\|` |
| 9 | `alias` | sim, sem `voices` | o que a voz recebe, até 200 caracteres. `-` significa "manter o original" |
| 10 | `voices` | não | exceções por voz: `antonio=x;thalita=-` |
| 11 | `entity` | não | identificador externo, como `Q317521` no Wikidata |

### Como cada tipo se comporta

| `kind` | Aplica quando | Exemplo |
|---|---|---|
| `n` | escrito com inicial maiúscula | `Musk` → `Mâsqui`; `musk` fica igual |
| `t` | em qualquer caixa, menos tudo em maiúsculas | `prompt` → `prômpti` |
| `s` | escrito todo em maiúsculas | `IA` → `Í-Á`; `ia` fica igual |

### Convenção de escrita para PT-BR

Escreva como um professor brasileiro de inglês escreveria no quadro:

- sílabas do português, com acento na tônica: `Élon Mâsqui`;
- uma vogal de apoio depois de consoante que não fecha sílaba: `prômpti`, não `prómpt`;
- siglas com hífen entre as letras: `Gê-Pê-U`.

### Regras que o validador impõe

- Ordem estritamente crescente de `key`, comparando **os bytes UTF-8**. Por isso `z`
  vem antes de `é`. Em Python: `sorted(keys, key=lambda k: k.encode('utf-8'))`. Em
  JavaScript, não use `localeCompare`; compare `TextEncoder().encode(k)` byte a byte.
- Sem chaves repetidas. Para duas pronúncias do mesmo termo, use `voices` ou `ipa`.
- Nenhum caractere de controle em `alias` ou `voices`. Nenhuma coluna pode conter TAB.
- `key` não começa com `#`.

Rode `python tools/dictionary.py validate` antes de enviar. O mesmo teste roda em todo
push, e o app repete a verificação depois de baixar: um arquivo inválido nunca
substitui o dicionário em uso.

## `manifest.json`

Gerado pela publicação. Não edite à mão. Esquema em
[`schema/manifest.schema.json`](../schema/manifest.schema.json).

```json
{
  "schema": 1,
  "dictionaries": {
    "pt-BR": {
      "format": 1,
      "revision": 1,
      "publishedAt": "2026-11-01T12:00:00Z",
      "entries": 37667,
      "url": "https://github.com/ivanpessanha/mi3-pronunciation-dictionary/releases/download/pt-BR-r1/lexicon-pt-BR-r1.tsv.gz",
      "size": 166545,
      "sha256": "…",
      "sourceSha256": "…"
    }
  }
}
```

| Campo | Significado |
|---|---|
| `revision` | inteiro que só cresce, por idioma. É o que define "versão nova" |
| `format` | um app que não conhece este formato ignora a entrada e não pergunta nada |
| `size`, `sha256` | do `.gz`; o app rejeita o download se não baterem |
| `entries` | linhas de dados; o app confere depois de descompactar |
| `sourceSha256` | do `lexicon.tsv`; evita publicar uma revisão sem mudança |

Endereço fixo que o app consulta:
`https://raw.githubusercontent.com/ivanpessanha/mi3-pronunciation-dictionary/main/manifest.json`

## Como o app decide

1. Ao abrir, baixa o manifesto. Sem internet, segue em silêncio.
2. Pergunta só se `revision` for maior que a do dicionário em uso, e maior que a última
   recusada. Com a pronúncia desativada nas configurações, não consulta nada.
3. Se o usuário aceitar, baixa, confere tamanho e SHA-256, valida todas as linhas e
   confere revisão, idioma e total de entradas. Só então troca o arquivo.
4. O app usa a maior revisão entre a embutida no APK e a baixada.

Uma correção muda o áudio apenas dos parágrafos cujo texto enviado à voz mudou.

## Outros idiomas

Crie `dictionaries/<locale>/lexicon.tsv` e publique com esse `locale`. O formato, o
validador, o manifesto e a publicação já tratam cada idioma de forma independente,
com sua própria sequência de revisões.

**O app ainda só lê `pt-BR`.** Antes de outro idioma chegar à voz, é preciso estender
`PronunciationService` no app: o escopo de vozes e a lista de locales consultados.

## Mudanças de formato

Colunas novas ou mudança de significado exigem `format` 2 e um app que o entenda.
Apps antigos ignoram a entrada e continuam com o dicionário que têm.
