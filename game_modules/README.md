# Directory for game modules

Put your Markdown-typed game modules here.

If your game module comes as one single file, as the default module _”Clean Up, Aisle Four!”_ does, you may choose to explicitly split the document into separate files, which may aid Cocai's retrieval:

```shell
uv run --with mdsplit -m mdsplit “your-game-module.md” -l 3 -t -o “your-game-module/”
```

To use your own game module, set `path` under `[game_module]` in `config.toml` to the directory containing the module's files:

```toml
[game_module]
path = “game_modules/your-game-module”
```

Then delete the old ChromaDB index and restart:

```shell
rm -rf .data/chroma/
just serve
```
