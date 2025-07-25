Todo before:

- [ ] fill out the env variables in `template-app.env`
- [ ] add posthog key or remove from compose
- [ ] add stripe key or remove from compose
- [ ] rename the project in `docker-compose.yml` at the `name` property
- [ ] remove nginx conf if not necessary
- [ ] run `npm i` and `poetry install` to setup tailwind and the dependencies

To run in production

```bash
./start prod
```

To run in dev

```bash
./start dev
```

To stop the container

```bash
./start stop
```
