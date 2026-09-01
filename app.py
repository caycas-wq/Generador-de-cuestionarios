import json
import docx
from google import genai
import pypdf
import streamlit as st

st.set_page_config(
    page_title="Generador de Cuestionarios", page_icon="📚", layout="centered"
)

st.title("📚 Generador de Cuestionarios por Secciones")
st.write(
    "Sube tu archivo (Word .docx, PDF o TXT) para generar preguntas"
    " interactivas."
)

api_key = st.text_input("Ingresa tu API Key de Google Gemini:", type="password")

uploaded_file = st.file_uploader(
    "Carga tu documento aquí", type=["docx", "pdf", "txt"]
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

if text_content and api_key:
  if st.button("🚀 Generar Cuestionario"):
    with st.spinner("Analizando documento con IA..."):
      try:
        client = genai.Client(api_key=api_key)

        prompt = f"""
                Analiza el siguiente texto y organízalo en sus secciones/temas principales.
                Para cada sección, genera entre 2 y 3 preguntas conceptuales de opción múltiple.
                Devuelve EXCLUSIVAMENTE un JSON válido con esta estructura exacta:
                {{
                  "sections": [
                    {{
                      "sectionTitle": "Nombre de la Sección",
                      "questions": [
                        {{
                          "question": "Pregunta...",
                          "options": ["Opción A", "Opción B", "Opción C"],
                          "correctIndex": 0,
                          "explanation": "Explicación de la respuesta..."
                        }}
                      ]
                    }}
                  ]
                }}

                Texto:
                {text_content[:15000]}
                """

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )

        st.session_state["quiz_data"] = json.loads(response.text)
      except Exception as e:
        st.error(f"Error al procesar el archivo: {e}")

if "quiz_data" in st.session_state:
  quiz = st.session_state["quiz_data"]
  for s_idx, sec in enumerate(quiz.get("sections", [])):
    st.header(f"📌 {sec['sectionTitle']}")
    for q_idx, q in enumerate(sec.get("questions", [])):
      st.subheader(f"{q_idx + 1}. {q['question']}")
      selected = st.radio(
          "Selecciona una respuesta:", q["options"], key=f"q_{s_idx}_{q_idx}"
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
