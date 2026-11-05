import flet as ft
import secrets
import string
import os
import json
from pathlib import Path
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from cryptography.fernet import Fernet
import base64

# --- Constantes de segurança ---
APP_NAME = "PasswordGen"
DATA_FILENAME = "senhas_criptografadas.bin"
LEGACY_FILE = "senhas_salvas.txt"

def get_data_file_path():
    """Retorna o caminho do arquivo de dados no diretório adequado do usuário."""
    if os.name == 'nt':  # Windows
        base_path = os.environ.get('APPDATA', os.path.expanduser('~'))
    else:
        base_path = os.path.expanduser('~/.config')

    app_dir = Path(base_path) / APP_NAME
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir / DATA_FILENAME

def get_legacy_file_path():
    """Retorna o caminho do arquivo legado na pasta atual."""
    return Path.cwd() / LEGACY_FILE

def derive_key(password: str, salt: bytes) -> bytes:
    """Deriva uma chave Fernet a partir da senha mestra usando PBKDF2HMAC."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
        backend=default_backend()
    )
    key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
    return key

def encrypt_data(data: dict, master_password: str) -> bytes:
    """Criptografa os dados usando a senha mestra."""
    salt = os.urandom(16)
    key = derive_key(master_password, salt)
    fernet = Fernet(key)

    json_data = json.dumps(data).encode()
    encrypted = fernet.encrypt(json_data)

    return salt + encrypted

def decrypt_data(encrypted_data: bytes, master_password: str) -> dict:
    """Descriptografa os dados usando a senha mestra."""
    salt = encrypted_data[:16]
    encrypted_payload = encrypted_data[16:]

    key = derive_key(master_password, salt)
    fernet = Fernet(key)

    decrypted = fernet.decrypt(encrypted_payload)
    return json.loads(decrypted.decode())

def migrate_legacy_data(master_password: str) -> bool:
    """Migra as senhas do arquivo legado para o formato criptografado."""
    legacy_path = get_legacy_file_path()

    if not legacy_path.exists():
        return True  # Nada a migrar

    try:
        with open(legacy_path, 'r', encoding='utf-8') as f:
            senhas = [line.strip() for line in f if line.strip()]

        if not senhas:
            return True

        data = {"senhas": senhas, "versao": 2}
        encrypted = encrypt_data(data, master_password)

        data_file = get_data_file_path()
        with open(data_file, 'wb') as f:
            f.write(encrypted)

        # Validar a migração tentando recuperar
        with open(data_file, 'rb') as f:
            test_data = decrypt_data(f.read(), master_password)

        if test_data.get("senhas", []) == senhas:
            return True
        return False
    except Exception:
        return False

def load_encrypted_data(master_password: str) -> dict:
    """Carrega e descriptografa os dados do arquivo."""
    data_file = get_data_file_path()

    if not data_file.exists():
        return {"senhas": [], "versao": 2}

    try:
        with open(data_file, 'rb') as f:
            encrypted_data = f.read()
        return decrypt_data(encrypted_data, master_password)
    except Exception:
        return None

def save_encrypted_data(data: dict, master_password: str):
    """Salva os dados criptografados no arquivo."""
    data_file = get_data_file_path()
    encrypted = encrypt_data(data, master_password)
    with open(data_file, 'wb') as f:
        f.write(encrypted)

# --- Variáveis de estado global ---
master_password_state = None  # None = não configurado, "" = configurado, "error" = erro
dados_usuario = {"senhas": []}
senha_atual = ""
senha_visivel = True

def main(page: ft.Page):
    global master_password_state, dados_usuario, senha_atual

    page.title = "Gerador de Senhas"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.window.width = 380
    page.window.height = 720
    page.window.resizable = False
    page.padding = 0
    page.bgcolor = ft.Colors.SURFACE

    # --- Funções ---
    def gerar_senha(e):
        nonlocal senha_atual
        comprimento = int(slider.value)
        caracteres = ""
        if upper_switch.value:
            caracteres += string.ascii_uppercase
        if lower_switch.value:
            caracteres += string.ascii_lowercase
        if numbers_switch.value:
            caracteres += string.digits
        if symbols_switch.value:
            caracteres += string.punctuation

        if caracteres:
            senha = "".join(secrets.choice(caracteres) for _ in range(comprimento))
            senha_output.value = senha if senha_visivel else "●" * len(senha)
            senha_atual = senha
            row_acoes.visible = True
            mostrar_btn.visible = True
            text_display.visible = False
        else:
            senha_output.value = "Selecione opções abaixo"
            senha_atual = ""
            row_acoes.visible = False
            mostrar_btn.visible = False
        page.update()

    def copiar_senha(e):
        nonlocal senha_atual
        if senha_atual and master_password_state is not None:
            try:
                page.set_clipboard(senha_atual)
                text_display.value = "Senha copiada!"
                text_display.color = ft.Colors.GREEN_400
            except Exception:
                text_display.value = "Erro ao copiar"
                text_display.color = ft.Colors.RED_400
            text_display.visible = True
            page.update()

    def salvar_senha(e):
        nonlocal dados_usuario
        if senha_atual and master_password_state is not None:
            dados_usuario["senhas"].append(senha_atual)
            save_encrypted_data(dados_usuario, master_password_state)
            text_display.value = "Senha salva com segurança!"
            text_display.color = ft.Colors.BLUE_400
            text_display.visible = True
            page.update()

    def limpar_senha(e):
        nonlocal senha_atual
        senha_atual = ""
        senha_output.value = ""
        text_display.visible = False
        row_acoes.visible = False
        mostrar_btn.visible = False
        page.update()

    def toggle_mostrar(e):
        nonlocal senha_visivel
        senha_visivel = not senha_visivel
        if senha_atual:
            senha_output.value = senha_atual if senha_visivel else "●" * len(senha_atual)
        mostrar_btn.content = ft.Row(
            [
                ft.Icon(ft.Icons.VISIBILITY_OFF if senha_visivel else ft.Icons.VISIBILITY, size=18),
                ft.Text("OCULTAR" if senha_visivel else "MOSTRAR", weight=ft.FontWeight.BOLD)
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=5
        )
        page.update()

    def toggle_theme(e):
        page.theme_mode = ft.ThemeMode.DARK if page.theme_mode == ft.ThemeMode.LIGHT else ft.ThemeMode.LIGHT
        theme_button.icon = ft.Icons.LIGHT_MODE if page.theme_mode == ft.ThemeMode.LIGHT else ft.Icons.DARK_MODE
        page.update()

    # --- Tela de configuração da senha mestra ---
    master_input = ft.TextField(
        label="Senha Mestra",
        password=True,
        can_reveal_password=False,
        width=280
    )

    master_confirm = ft.TextField(
        label="Confirmar Senha Mestra",
        password=True,
        can_reveal_password=False,
        width=280
    )

    master_error = ft.Text("", color=ft.Colors.RED, visible=False, size=12)

    def configurar_master(e):
        nonlocal master_password_state, dados_usuario
        senha_digitada = master_input.value
        senha_confirmar = master_confirm.value

        if not senha_digitada or len(senha_digitada) < 6:
            master_error.value = "A senha mestra deve ter pelo menos 6 caracteres"
            master_error.visible = True
            page.update()
            return

        if senha_digitada != senha_confirmar:
            master_error.value = "As senhas não coincidem"
            master_error.visible = True
            page.update()
            return

        # Tentar carregar dados existentes
        dados_carregados = load_encrypted_data(senha_digitada)

        if dados_carregados is not None:
            dados_usuario = dados_carregados
        else:
            # Primeiro uso - criar novo arquivo
            dados_usuario = {"senhas": [], "versao": 2}
            save_encrypted_data(dados_usuario, senha_digitada)
            # Tentar migrar dados legados
            migrate_legacy_data(senha_digitada)

        master_password_state = senha_digitada
        master_screen.visible = False
        page.update()

    master_screen = ft.Container(
        content=ft.Column(
            [
                ft.Text("Configurar Senha Mestre", size=20, weight="bold"),
                ft.Text("Sua senha mestre protege todos os arquivos salvos.\nElaborada uma senha forte ajuda a proteger suas credenciais.",
                       size=14, color=ft.Colors.OUTLINE),
                ft.Divider(),
                master_input,
                master_confirm,
                master_error,
                ft.Button(
                    content=ft.Text("CONTINUAR", weight=ft.FontWeight.BOLD),
                    on_click=configurar_master,
                    bgcolor=ft.Colors.PRIMARY,
                    color=ft.Colors.ON_PRIMARY,
                    style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), padding=ft.Padding.all(15)),
                    width=200
                )
            ],
            spacing=15,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        ),
        alignment=ft.alignment.center,
        bgcolor=ft.Colors.SURFACE,
        border_radius=20,
        padding=30
    )

    # --- Tela de verificação de senha mestre ---
    unlock_input = ft.TextField(
        label="Digite sua senha mestre",
        password=True,
        can_reveal_password=False,
        width=280
    )

    unlock_error = ft.Text("", color=ft.Colors.RED, visible=False, size=12)

    def verificar_master(e):
        nonlocal master_password_state, dados_usuario
        senha_digitada = unlock_input.value

        # Tentar carregar com a senha digitada
        dados_carregados = load_encrypted_data(senha_digitada)

        if dados_carregados is None:
            unlock_error.value = "Senha mestre incorreta ou dados corrompidos"
            unlock_error.visible = True
            page.update()
            return

        dados_usuario = dados_carregados
        master_password_state = senha_digitada
        unlock_screen.visible = False
        page.update()

    unlock_screen = ft.Container(
        content=ft.Column(
            [
                ft.Text("Acesso às Senhas", size=20, weight="bold"),
                ft.Text("Digite sua senha mestre para acessar e gerenciar as senhas salvas.",
                       size=14, color=ft.Colors.OUTLINE),
                ft.Divider(),
                unlock_input,
                unlock_error,
                ft.Row(
                    [
                        ft.Button(
                            content=ft.Text("VERIFICAR", weight=ft.FontWeight.BOLD),
                            on_click=verificar_master,
                            bgcolor=ft.Colors.PRIMARY,
                            color=ft.Colors.ON_PRIMARY,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), padding=ft.Padding.all(15)),
                            width=150
                        ),
                        ft.Button(
                            content=ft.Text("CRIAR", weight=ft.FontWeight.BOLD),
                            on_click=lambda e: (setattr(master_screen, 'visible', True), setattr(unlock_screen, 'visible', False), page.update()),
                            bgcolor=ft.Colors.TERTIARY,
                            color=ft.Colors.ON_TERTIARY,
                            style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10), padding=ft.Padding.all(15)),
                            width=150
                        )
                    ],
                    alignment=ft.MainAxisAlignment.CENTER,
                    spacing=15
                )
            ],
            spacing=15,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        ),
        alignment=ft.alignment.center,
        bgcolor=ft.Colors.SURFACE,
        border_radius=20,
        padding=30
    )

    # --- Mensagem de aviso sobre recuperação ---
    recovery_warning = ft.Text(
        "⚠️ Se esquecer a senha mestre, os dados não poderão ser recuperados.\nGuarde-a em um local seguro.",
        color=ft.Colors.OUTLINE,
        size=12,
        text_align=ft.TextAlign.CENTER,
        visible=False
    )

    # --- Tela principal (apenas aparece após autenticação) ---
    theme_button = ft.IconButton(
        icon=ft.Icons.LIGHT_MODE,
        on_click=toggle_theme,
        icon_size=24,
        tooltip="Alternar Tema"
    )

    header = ft.Container(
        content=ft.Row(
            [
                ft.Text("Password Gen", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY),
                theme_button
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        ),
        padding=ft.Padding.only(left=25, right=15, top=20, bottom=10)
    )

    senha_output = ft.TextField(
        value="",
        hint_text="Sua senha aparecerá aqui",
        read_only=True,
        text_align=ft.TextAlign.CENTER,
        text_size=20,
        text_vertical_align=0,
        bgcolor=ft.Colors.SURFACE,
        border_radius=15,
        border_color=ft.Colors.PRIMARY_CONTAINER,
        focused_border_color=ft.Colors.PRIMARY,
        text_style=ft.TextStyle(font_family="monospace", weight=ft.FontWeight.W_500),
        height=70,
    )

    text_display = ft.Text(value="", size=12, weight=ft.FontWeight.BOLD, visible=False)

    btn_style = ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=10),
        padding=ft.Padding.all(15)
    )

    copiar_btn = ft.Button(
        content=ft.Row([ft.Icon(ft.Icons.COPY, size=18), ft.Text("COPIAR")], spacing=5),
        on_click=copiar_senha,
        bgcolor=ft.Colors.SECONDARY,
        color=ft.Colors.ON_SECONDARY,
        style=btn_style,
        expand=True
    )

    salvar_btn = ft.Button(
        content=ft.Row([ft.Icon(ft.Icons.SAVE, size=18), ft.Text("SALVAR")], spacing=5),
        on_click=salvar_senha,
        bgcolor=ft.Colors.TERTIARY,
        color=ft.Colors.ON_TERTIARY,
        style=btn_style,
        expand=True
    )

    limpar_btn = ft.IconButton(
        icon=ft.Icons.DELETE_OUTLINE,
        icon_color=ft.Colors.RED_400,
        on_click=limpar_senha,
        tooltip="Limpar tudo"
    )

    row_acoes = ft.Row(
        [copiar_btn, salvar_btn, limpar_btn],
        visible=False,
        spacing=10
    )

    mostrar_btn = ft.Button(
        content=ft.Row(
            [ft.Icon(ft.Icons.VISIBILITY_OFF, size=18), ft.Text("OCULTAR", weight=ft.FontWeight.BOLD)],
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=5
        ),
        on_click=toggle_mostrar,
        bgcolor=ft.Colors.PRIMARY_CONTAINER,
        color=ft.Colors.ON_PRIMARY_CONTAINER,
        style=btn_style,
        visible=False,
        width=200
    )

    slider = ft.Slider(
        min=8, max=32, value=12,
        divisions=24, label="{value} caracteres",
        active_color=ft.Colors.PRIMARY
    )

    upper_switch = ft.Switch(value=True, active_color=ft.Colors.PRIMARY)
    lower_switch = ft.Switch(value=True, active_color=ft.Colors.PRIMARY)
    numbers_switch = ft.Switch(value=True, active_color=ft.Colors.PRIMARY)
    symbols_switch = ft.Switch(value=False, active_color=ft.Colors.PRIMARY)

    settings_card = ft.Container(
        content=ft.Column(
            [
                ft.Text("CONFIGURAÇÕES", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.OUTLINE),
                ft.Column([
                    ft.Text("Comprimento da Senha", size=14),
                    slider,
                ], spacing=0),
                ft.Divider(height=1, color=ft.Colors.OUTLINE_VARIANT),
                ft.Row([ft.Text("Letras Maiúsculas"), upper_switch], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([ft.Text("Letras Minúsculas"), lower_switch], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([ft.Text("Incluir Números"), numbers_switch], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Row([ft.Text("Incluir Símbolos"), symbols_switch], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ],
            spacing=15
        ),
        padding=20,
        bgcolor=ft.Colors.SURFACE,
        border_radius=20,
    )

    gerar_button = ft.Button(
        content=ft.Text("GERAR SENHA", size=16, weight=ft.FontWeight.BOLD),
        on_click=gerar_senha,
        bgcolor=ft.Colors.PRIMARY,
        color=ft.Colors.ON_PRIMARY,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=15),
            padding=ft.Padding.all(20)
        ),
        height=60,
        width=300
    )

    # Layout principal - mostra tela de unlock ou principal conforme estado
    main_content = ft.Column(
        [
            header,
            ft.Container(
                content=ft.Column(
                    [
                        senha_output,
                        ft.Container(text_display, alignment=ft.alignment.center),
                        row_acoes,
                        ft.Container(mostrar_btn, alignment=ft.alignment.center),
                        ft.VerticalDivider(thickness=1, color=ft.Colors.TRANSPARENT),
                        settings_card,
                        ft.VerticalDivider(thickness=1, color=ft.Colors.TRANSPARENT),
                        ft.Container(gerar_button, alignment=ft.alignment.center),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=10
                ),
                padding=25
            )
        ],
        scroll=ft.ScrollMode.ADAPTIVE
    )

    page.add(
        ft.Stack(
            [
                unlock_screen,
                main_content
            ],
            expand=True
        )
    )

ft.run(main, assets_dir="assets")