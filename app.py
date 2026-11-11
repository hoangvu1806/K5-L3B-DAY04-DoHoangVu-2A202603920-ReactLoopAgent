"""Web UI cho demo agent: FastAPI + Jinja2. Chạy: python -m uvicorn app:app --reload"""
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from agent import run_agent
from bonus.tools import BonusTools
from demo import DEMO_CASES, summarize
from providers import Provider
from status_tools import StatusTools

ROOT = Path(__file__).resolve().parent


def load_env_file(path):
    """Đọc dòng `export KEY=VALUE` trong .env; không ghi đè biến đã có trong shell."""
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        line = line.removeprefix('export ').strip()
        key, sep, value = line.partition('=')
        if sep and key.strip():
            os.environ.setdefault(key.strip(), value.strip().strip('\'"'))


load_env_file(ROOT / '.env')

app = FastAPI(title='Status Investigation Agent')
templates = Jinja2Templates(directory=str(ROOT / 'templates'))


class AskRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    mode: str = Field(default='core', pattern='^(core|bonus)$')


@app.get('/', response_class=HTMLResponse)
def index(request: Request):
    samples = {'core': [c for c in DEMO_CASES if c['tools'] == 'core'],
               'bonus': [c for c in DEMO_CASES if c['tools'] == 'bonus']}
    return templates.TemplateResponse(request, 'index.html', {
        'samples': samples, 'model': os.getenv('MODEL'), 'provider': os.getenv('PROVIDER')})


@app.post('/api/ask')
def ask(body: AskRequest):
    try:
        provider = Provider(os.getenv('PROVIDER', 'openai'), os.getenv('MODEL'))
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    bonus = body.mode == 'bonus'
    tools = BonusTools() if bonus else StatusTools()
    result = run_agent(body.query.strip(), provider, tools, max_steps=16 if bonus else 8)
    case = {'id': 'web', 'level': '', 'tools': body.mode, 'query': body.query}
    return summarize(case, result)
