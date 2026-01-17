from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from datetime import datetime
import sqlite3
import base64
import os
from typing import Optional

app = FastAPI()

# Permitir que Flutter se conecte
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Crear carpeta para imágenes
os.makedirs("imagenes", exist_ok=True)

# Crear base de datos SQLite con timeout y check_same_thread
def init_db():
    conn = sqlite3.connect('notas.db', timeout=10, check_same_thread=False)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mensaje TEXT NOT NULL,
            imagen TEXT,
            fecha TEXT NOT NULL,
            color TEXT DEFAULT '#FFEBEE'
        )
    ''')
    conn.commit()
    conn.close()

# Inicializar DB al arrancar
init_db()

# Modelo de nota
class Nota(BaseModel):
    mensaje: str
    imagen_base64: Optional[str] = None
    color: Optional[str] = '#FFEBEE'  # Color por defecto (rosa claro)

def get_db():
    conn = sqlite3.connect('notas.db', timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

@app.post("/notas")
async def crear_nota(nota: Nota):
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        imagen_path = None
        if nota.imagen_base64:
            # Guardar imagen
            imagen_data = base64.b64decode(nota.imagen_base64)
            imagen_nombre = f"img_{datetime.now().timestamp()}.jpg"
            imagen_path = f"imagenes/{imagen_nombre}"
            with open(imagen_path, "wb") as f:
                f.write(imagen_data)
        
        cursor.execute(
            'INSERT INTO notas (mensaje, imagen, fecha, color) VALUES (?, ?, ?, ?)',
            (nota.mensaje, imagen_path, fecha, nota.color)
        )
        conn.commit()
        nota_id = cursor.lastrowid
        
        return {
            "success": True,
            "nota": {
                "id": nota_id,
                "mensaje": nota.mensaje,
                "imagen": imagen_path,
                "fecha": fecha,
                "color": nota.color
            }
        }
    finally:
        if conn:
            conn.close()

@app.get("/notas")
async def obtener_notas():
    print("🔵 Petición GET /notas recibida")
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM notas ORDER BY id DESC')
        rows = cursor.fetchall()
        
        notas = []
        for row in rows:
            nota = {
                "id": row["id"],
                "mensaje": row["mensaje"],
                "fecha": row["fecha"],
                "tiene_imagen": row["imagen"] is not None,
                "imagen_url": f"/imagenes/{row['id']}" if row["imagen"] else None,
                "color": row["color"] if row["color"] else '#FFEBEE'
            }
            notas.append(nota)
        
        print(f"✅ Devolviendo {len(notas)} notas")
        return {"notas": notas}
    except Exception as e:
        print(f"❌ Error en GET /notas: {e}")
        raise
    finally:
        if conn:
            conn.close()

@app.get("/imagenes/{nota_id}")
async def obtener_imagen(nota_id: int):
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT imagen FROM notas WHERE id = ?', (nota_id,))
        row = cursor.fetchone()
        
        if row and row["imagen"] and os.path.exists(row["imagen"]):
            return FileResponse(row["imagen"])
        return {"error": "Imagen no encontrada"}
    finally:
        if conn:
            conn.close()

@app.delete("/notas/{nota_id}")
async def eliminar_nota(nota_id: int):
    conn = None
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Obtener imagen antes de eliminar
        cursor.execute('SELECT imagen FROM notas WHERE id = ?', (nota_id,))
        row = cursor.fetchone()
        
        # Eliminar imagen del disco si existe
        if row and row["imagen"] and os.path.exists(row["imagen"]):
            os.remove(row["imagen"])
        
        cursor.execute('DELETE FROM notas WHERE id = ?', (nota_id,))
        conn.commit()
        return {"success": True}
    finally:
        if conn:
            conn.close()

@app.get("/")
async def root():
    return {"mensaje": "API de Notas con fotos para mi novio ❤️"}

# Para correr: uvicorn main:app --reload --host 0.0.0.0 --port 8000