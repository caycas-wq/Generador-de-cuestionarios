import json
import os
import docx
from github import Github
from google import genai
import pypdf
import streamlit as st

st.set_page_config(
    page_title="Generador de Cuestionarios", page_icon="📚", layout="centered"
)

# --- OBTENER CREDENCIALES DESDE SECRETS O MANUAL ---
gemini_key = st.secrets.get("GEMINI_API_KEY", "")
github_token = st.secrets.get("GITHUB_TOKEN", "")
repo_name = st.secrets.get("REPO_NAME", "caycas-wq/Generador-de-cuestionarios")

st.title("📚 Generador de Cuestionarios Personalizable")

# --- FUNCIONES DE GITHUB ---
def get_github_repo():
  if github_token and repo_name:
    try:
      g = Github(github_token)
      return g.get_repo(repo_name)
    except Exception as e:
      st.error(f"Error al conectar con GitHub: {e}")
  return None


def list_cloud_quizzes(repo):
  quizzes = []
  if repo:
    try:
      contents = repo.get_contents("quizzes")
      for content_file in contents:
        if content_file.name.endswith(".json"):
          quizzes.append(content_file.name)
    except Exception:
      # Si la carpeta quizzes no existe aún, se creará al guardar el primero
      pass
  return quizzes


def save_quiz_to_github(repo, file_name, json_data):
  if repo:
    path = f"quizzes/{file_name}.json"
    content = json.dumps(json_data, ensure_ascii=False, indent=2)
    try:
      # Intentar actualizar si ya existe
      existing_file = repo.get_contents(path)
      repo.update_file(
          path,
          f"Actualizar cuestionario: {file_name}",
          content,
          existing_file.sha,
      )
      return True, "Cuestionario actualizado en GitHub con éxito."
    except Exception:
      # Crear nuevo archivo si no existe
      try:
        repo.create_file(
            path, f"Añadir cuestionario: {file_name}", content
        )
        return True, "Cuestionario guardado en la nube de GitHub con éxito."
      except Exception as e:
        return False, f"Error al guardar en GitHub: {e}"
  return False, "No hay conexión con el repositorio de GitHub."


def load_quiz_from_github(repo, file_name):
  if repo:
    try:
      file_content = repo.get_contents(f"quizzes/{file_name}")
      return json.loads(file_content.decoded_content.decode("utf-8"))
    except Exception as e:
      st.error(f"Error al descargar desde GitHub: {e}")
  return None


repo = get_github_repo()

# --- BARRA LATERAL ---
with st.sidebar:
  st.header("⚙️ Configuración")

  if not gemini_key:
    gemini_key = st.text_input("API Key de Google Gemini:", type="password")

  st.divider()
  st.subheader("🎯 Parámetros de Cuestionario")

  questions_per_section = st.slider(
      "Preguntas por sección:", min_value=1, max_value=10, value=3
  )

  difficulty = st.selectbox(
      "Nivel de Dificultad:",
      ["Fácil (Directa)", "Intermedio (Análisis)", "Avanzado (Casos Prácticos)"],
      index=1,
  )

  question_type = st.selectbox(
      "Tipo de Preguntas:",
      ["Opción Múltiple (4 opciones)", "Verdadero / Falso", "Combinado"],
  )

  st.divider()

  # --- EXPLORADOR DE CUESTIONARIOS EN LA NUBE ---
  st.header("☁️ Cuestionarios en la Nube")
  cloud_quizzes = list_cloud_quizzes(repo)

  if cloud_quizzes:
    selected_cloud_quiz = st.selectbox(
        "Selecciona un cuestionario:",
        options=["-- Seleccionar --"] + cloud_quizzes,
    )

    if selected_cloud_quiz != "-- Seleccionar --":
      if st.button("📖 Cargar desde Nube"):
        loaded = load_quiz_from_github(repo, selected_cloud_quiz)
        if loaded:
          st.session_state["quiz_data"] = loaded
          st.session_state["active_title"] = selected_cloud_quiz.replace(
              ".json", ""
          )
          st.success(f"Cargado: {selected_cloud_quiz}")
  else:
    st.info("No hay cuestionarios guardados aún en el repositorio.")

# --- ÁREA PRINCIPAL ---
uploaded_file = st.file_uploader(
    "Carga un nuevo documento (Word .docx, PDF o TXT)",
    type=["docx", "pdf", "txt"],
)

text_content = ""

if uploaded_file is not None:
  if uploaded_file.name.endswith(".docx"):
    doc = docx.Document(uploaded_file)
    text_content = "\n".join([para.text for para in doc.paragraphs if para.text])
  elif uploaded_file.name.endswith(".pdf"):
    reader = pypdf.PdfReader(uploaded_file)
    for page in reader.pages:
      text_content += page.extract_text() + "\n"
  elif uploaded_file.name.endswith(".txt"):
    text_content = uploaded_file.read().decode("utf-8")

if text_content and gemini_key:
  if st.button("🚀 Generar Nuevo Cuestionario"):
    with st.spinner("Analizando documento con IA y guardando estructura..."):
      try:
        client = genai.Client(api_key=gemini_key)

        prompt = f"""
                Analiza el siguiente texto y organízalo en sus secciones/temas principales.
                Para cada sección, genera exactamente {questions_per_section} preguntas.

                CONFIGURACIÓN PEDAGÓGICA:
                - Nivel de dificultad: {difficulty}.
                - Tipo de pregunta deseado: {question_type}.

                REGLAS CRÍTICAS PARA LAS OPCIONES:
                1. Para Opción Múltiple: Genera 4 alternativas donde TODAS (correctas e incorrectas) tengan una longitud, complejidad y tono similar.
                2. Para Verdadero/Falso: Genera únicamente 2 opciones: ["Verdadero", "Falso"].
                3. NUNCA hagas que la opción correcta sea visiblemente más larga o detallada que los distractores.

                Devuelve EXCLUSIVAMENTE un JSON válido con esta estructura exacta:
                {{
                  "sections": [
                    {{
                      "sectionTitle": "Nombre de la Sección",
                      "questions": [
                        {{
                          "question": "Pregunta...",
                          "options": ["Opción A", "Opción B", "Opción C", "Opción D"],
                          "correctIndex": 0,
                          "explanation": "Explicación detallada..."
                        }}
                      ]
                    }}
                  ]
                }}

                Texto:
                {text_content[:20000]}
                """

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )

        st.session_state["quiz_data"] = json.loads(response.text)
        st.session_state["active_title"] = (
            uploaded_file.name.rsplit(".", 1)[0].capitalize()
        )
      except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")

elif not gemini_key and uploaded_file:
  st.warning("⚠️ Por favor ingresa tu API Key en los Secrets o en la barra lateral.")

# --- RENDERIZADO Y GUARDADO EN LA NUBE ---
if "quiz_data" in st.session_state:
  st.divider()

  col1, col2 = st.columns([2, 1])
  with col1:
    save_title = st.text_input(
        "Nombre para el archivo en GitHub:",
        value=st.session_state.get("active_title", "Cuestionario"),
    )
  with col2:
    st.write(" ")
    st.write(" ")
    if st.button("☁️ Guardar en GitHub"):
      if repo:
        success, msg = save_quiz_to_github(
            repo, save_title, st.session_state["quiz_data"]
        )
        if success:
          st.success(msg)
          st.rerun()
        else:
          st.error(msg)
      else:
        st.error(
            "Falta configurar el GITHUB_TOKEN en los Secrets de Streamlit."
        )

  st.divider()

  quiz = st.session_state["quiz_data"]
  for s_idx, sec in enumerate(quiz.get("sections", [])):
    st.header(f"📌 {sec['sectionTitle']}")
    for q_idx, q in enumerate(sec.get("questions", [])):
      st.subheader(f"{q_idx + 1}. {q['question']}")
      selected = st.radio(
          "Selecciona tu respuesta:", q["options"], key=f"q_{s_idx}_{q_idx}"
      )
      if st.button(
          f"Comprobar respuesta {q_idx + 1}", key=f"btn_{s_idx}_{q_idx}"
      ):
        correct_option = q["options"][q["correctIndex"]]
        if selected == correct_option:
          st.success(f"¡Correcto! {q['explanation']}")
        else:
          st.error(
              f"Incorrecto. La respuesta correcta era:"
              f" {correct_option}.\n\nExplicación: {q['explanation']}"
          )
