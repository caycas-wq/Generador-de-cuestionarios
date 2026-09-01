import json
import time
import docx
from github import Github, BadCredentialsException
from google import genai
import pypdf
import streamlit as st

st.set_page_config(
    page_title="Generador de Cuestionarios", page_icon="📚", layout="centered"
)

st.title("📚 Generador de Cuestionarios Personalizable")

# --- OBTENER CREDENCIALES ---
gemini_key = st.secrets.get("GEMINI_API_KEY", "")
github_token = st.secrets.get("GITHUB_TOKEN", "")
repo_name = st.secrets.get("REPO_NAME", "caycas-wq/Generador-de-cuestionarios")

# --- BARRA LATERAL ---
with st.sidebar:
  st.header("⚙️ Configuración")

  if not gemini_key:
    gemini_key = st.text_input("API Key de Google Gemini:", type="password")

  st.divider()
  st.subheader("🔑 Token de GitHub")

  custom_token = st.text_input(
      "Token GitHub (ghp_...):",
      value=github_token,
      type="password",
      help="Si sale error 401, pega aquí tu nuevo token de GitHub.",
  )
  active_token = custom_token if custom_token else github_token

  st.divider()
  st.subheader("🎯 Parámetros")

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

# --- CONEXIÓN SEGURA CON GITHUB ---
repo = None
if active_token and repo_name:
  try:
    g = Github(active_token)
    repo = g.get_repo(repo_name)
    _ = repo.name
  except BadCredentialsException:
    st.error(
        "⚠️ El Token de GitHub es inválido (Error 401). Verifica o pega uno"
        " nuevo en la barra lateral."
    )
    repo = None
  except Exception as e:
    st.warning(f"No se pudo conectar a GitHub: {e}")

# --- HISTORIAL EN LA NUBE ---
if repo:
  with st.sidebar:
    st.divider()
    st.header("☁️ Cuestionarios Guardados")
    try:
      contents = repo.get_contents("quizzes")
      cloud_quizzes = [f.name for f in contents if f.name.endswith(".json")]
      if cloud_quizzes:
        selected_quiz = st.selectbox(
            "Selecciona:", ["-- Seleccionar --"] + cloud_quizzes
        )
        if selected_quiz != "-- Seleccionar --" and st.button("📖 Cargar"):
          file_content = repo.get_contents(f"quizzes/{selected_quiz}")
          st.session_state["quiz_data"] = json.loads(
              file_content.decoded_content.decode("utf-8")
          )
          st.session_state["active_title"] = selected_quiz.replace(".json", "")
          st.success("Cargado con éxito")
    except Exception:
      st.info("No hay cuestionarios guardados aún en la carpeta /quizzes.")

# --- CARGA DE ARCHIVOS Y GENERACIÓN CON RESPALDO ---
uploaded_file = st.file_uploader(
    "Carga un nuevo documento (Word .docx, PDF o TXT)",
    type=["docx", "pdf", "txt"],
)

text_content = ""

if uploaded_file is not None:
  if uploaded_file.name.endswith(".docx"):
    doc = docx.Document(uploaded_file)
    text_content = "\n".join(
        [para.text for para in doc.paragraphs if para.text]
    )
  elif uploaded_file.name.endswith(".pdf"):
    reader = pypdf.PdfReader(uploaded_file)
    for page in reader.pages:
      text_content += page.extract_text() + "\n"
  elif uploaded_file.name.endswith(".txt"):
    text_content = uploaded_file.read().decode("utf-8")

if text_content and gemini_key:
  if st.button("🚀 Generar Nuevo Cuestionario"):
    with st.spinner("Analizando documento con IA..."):
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

      # Lista de modelos a probar secuencialmente si el servidor está ocupado
      candidate_models = [
          "gemini-2.5-flash",
          "gemini-2.5-flash-lite",
          "gemini-1.5-flash",
      ]

      success = False
      last_error = None

      for model_name in candidate_models:
        for attempt in range(2):  # Hasta 2 reintentos por modelo
          try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
            st.session_state["quiz_data"] = json.loads(response.text)
            st.session_state["active_title"] = (
                uploaded_file.name.rsplit(".", 1)[0].capitalize()
            )
            success = True
            break
          except Exception as e:
            last_error = e
            time.sleep(2)  # Esperar 2 segundos antes de reintentar
        if success:
          break

      if not success:
        st.error(
            f"Los servidores de Gemini se encuentran saturados en este momento."
            f" Detalles: {last_error}"
        )

# --- MOSTRAR Y GUARDAR CUESTIONARIO ---
if "quiz_data" in st.session_state:
  st.divider()

  col1, col2 = st.columns([2, 1])
  with col1:
    save_title = st.text_input(
        "Nombre del cuestionario:",
        value=st.session_state.get("active_title", "Cuestionario"),
    )
  with col2:
    st.write(" ")
    st.write(" ")
    if st.button("☁️ Guardar en GitHub"):
      if repo:
        try:
          path = f"quizzes/{save_title}.json"
          content = json.dumps(
              st.session_state["quiz_data"], ensure_ascii=False, indent=2
          )
          try:
            old_file = repo.get_contents(path)
            repo.update_file(
                path, f"Update {save_title}", content, old_file.sha
            )
          except Exception:
            repo.create_file(path, f"Add {save_title}", content)
          st.success("¡Guardado en la nube de GitHub con éxito!")
        except Exception as e:
          st.error(f"Error al guardar: {e}")
      else:
        st.error("Se requiere un Token de GitHub válido para guardar.")

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
