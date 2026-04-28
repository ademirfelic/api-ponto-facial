from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import numpy as np
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from database import get_connection
import json

app = FastAPI()


class CadastroEmbedding(BaseModel):
    funcionario_id: int
    embedding: list[float]


class RegistroEmbedding(BaseModel):
    embedding: list[float]


# ==============================
# NORMALIZAR
# ==============================
def normalizar(v):
    v = np.array(v, dtype=np.float32)
    return v / np.linalg.norm(v)


# ==============================
# CADASTRO
# ==============================
@app.post("/cadastrar")
async def cadastrar(data: CadastroEmbedding):
    try:
        embedding = normalizar(data.embedding)

        conn = get_connection()
        cursor = conn.cursor()

        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))

        cursor.execute("""
            INSERT INTO reconhecimento (rec_funcionario, rec_embedding, rec_criado_em)
            VALUES (%s, %s, %s)
        """, (
            data.funcionario_id,
            json.dumps(embedding.tolist()),
            agora.date()
        ))

        conn.commit()
        cursor.close()
        conn.close()

        return {"status": "ok"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ==============================
# REGISTRO
# ==============================
@app.post("/registrar-ponto")
async def registrar_ponto(data: RegistroEmbedding):
    try:
        embedding_atual = normalizar(data.embedding)

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT rec_funcionario, rec_embedding, fun_nome
            FROM reconhecimento
            JOIN tb_funcionarios ON rec_funcionario = fun_id
        """)

        registros = cursor.fetchall()

        melhor_match = None
        menor_distancia = 999
        nome = ""

        for r in registros:
            emb = np.array(json.loads(r["rec_embedding"]), dtype=np.float32)

            distancia = np.linalg.norm(embedding_atual - emb)

            if distancia < menor_distancia:
                menor_distancia = distancia
                melhor_match = r["rec_funcionario"]
                nome = r["fun_nome"]

        cursor.close()
        conn.close()

        print("DISTANCIA:", menor_distancia)

        # 🔥 threshold ajustável
        if menor_distancia < 1.3:

            agora = datetime.now(ZoneInfo("America/Sao_Paulo"))

            conn = get_connection()
            cursor = conn.cursor(dictionary=True)

            cursor.execute("""
                SELECT hor_hora
                FROM tb_horas
                WHERE hor_fun_id = %s
                AND hor_data = %s
                ORDER BY hor_id DESC
                LIMIT 1
            """, (melhor_match, agora.date()))

            ultimo = cursor.fetchone()

            if ultimo:
                ultima_hora = ultimo["hor_hora"]

                if isinstance(ultima_hora, timedelta):
                    ultima = datetime.combine(agora.date(), datetime.min.time()) + ultima_hora
                elif isinstance(ultima_hora, str):
                    ultima = datetime.combine(
                        agora.date(),
                        datetime.strptime(ultima_hora, "%H:%M:%S").time()
                    )
                else:
                    ultima = datetime.combine(agora.date(), ultima_hora)

                if agora - ultima < timedelta(minutes=5):
                    return {
                        "status": "erro",
                        "msg": "Ponto já registrado",
                        "nome": nome
                    }

            cursor.execute("""
                INSERT INTO tb_horas
                (hor_hora, hor_data, hor_fun_id, hor_semana, hor_status)
                VALUES (%s, %s, %s, %s, %s)
            """, (
                agora.time(),
                agora.date(),
                melhor_match,
                agora.strftime("%A"),
                1
            ))

            conn.commit()
            cursor.close()
            conn.close()

            return {
                "status": "ok",
                "nome": nome,
                "distancia": float(menor_distancia)
            }

        return {
            "status": "erro",
            "msg": "Rosto não reconhecido",
            "distancia": float(menor_distancia)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))