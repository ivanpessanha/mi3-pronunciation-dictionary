# Dicionário de pronúncia do Mi3 Voice Reader

Dicionário global que o [Mi3 Voice Reader](https://github.com/ivanpessanha/mi3_ebook_voice_reader)
usa para que as vozes neurais pronunciem bem nomes, siglas e termos estrangeiros.
Por enquanto há só `pt-BR`, mas a estrutura aceita outros idiomas.

| Texto | Enviado à voz |
|---|---|
| GPU | Gê-Pê-U |
| Elon Musk | Élon Mâsqui |
| prompt | prômpti |

O formato completo está em [docs/FORMAT.md](docs/FORMAT.md).

## Editar

Altere `dictionaries/<locale>/lexicon.tsv` e valide. Requer apenas Python 3:

```sh
python tools/dictionary.py validate
python -m unittest discover -s tests
```

Enviar um commit não afeta os usuários.

## Publicar

Rode o fluxo **Publish dictionary** na aba Actions, ou pela API:

```sh
gh workflow run publish.yml -R ivanpessanha/mi3-pronunciation-dictionary -f locale=pt-BR
```

O fluxo valida o arquivo, cria a Release `pt-BR-r<N>` com o `.gz` e atualiza
`manifest.json`. Se o conteúdo não mudou, não publica nada. Depois disso, cada app
pergunta ao usuário, na abertura seguinte, se quer baixar a nova versão.

## Licença

Consulte [NOTICE.md](NOTICE.md): o dicionário tem dados derivados de fontes abertas.
