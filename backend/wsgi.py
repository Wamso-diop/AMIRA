from dotenv import load_dotenv

from amira import create_app

load_dotenv()  # avant create_app, qui lit os.environ
app = create_app()
