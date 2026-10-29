import modal

app = modal.App.lookup("bug2pr", create_if_missing=True)
sb = modal.Sandbox.create(app=app)
p = sb.exec("python", "-c", "print('hello from the sandbox')", timeout=30)
print(p.stdout.read())
sb.terminate()