from flask_login import UserMixin

class Usuario(UserMixin):
    def __init__(
        self,
        id: int,
        username: str,
        email: str,
        senha: str,
        role: str,
        loja_id: int = None,     # corresponde ao campo da tabela
        criado_em: str = None
    ):
        self.id = id
        self.username = username
        self.email = email
        self.senha = senha
        self.role = role
        self.loja_id = loja_id   # agora corresponde ao banco
        self.criado_em = criado_em

    def __repr__(self) -> str:
        return f"<Usuario id={self.id} username={self.username} role={self.role} loja_id={self.loja_id}>"

    def get_id(self) -> str:
        return str(self.id)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def is_user(self) -> bool:
        return self.role == "user"
