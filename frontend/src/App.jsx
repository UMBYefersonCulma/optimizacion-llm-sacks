import React, { useState } from "react";
import axios from "axios";

function App() {
  const [edad, setEdad] = useState("");
  const [sexo, setSexo] = useState("Masculino");
  const [frase, setFrase] = useState("");
  const [resultado, setResultado] = useState(null);
  const [loteResultados, setLoteResultados] = useState([]);
  const [csvData, setCsvData] = useState([]);
  const [cargando, setCargando] = useState(false);
  const [tiempoInicio, setTiempoInicio] = useState(null);
  const [tiempoFinal, setTiempoFinal] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setCargando(true);
    setTiempoInicio(Date.now());
    setTiempoFinal(null);

    try {
      const response = await axios.post("http://localhost:5000/clasificar", {
        edad,
        sexo,
        frase,
      });
      setResultado(response.data.resultado);
    } catch (error) {
      setResultado("❌ Error al clasificar la frase.");
    } finally {
      setCargando(false);
      setTiempoFinal(Date.now());
    }
  };

  const handleCSVUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = async (event) => {
      const text = event.target.result;
      const lines = text.split("\n").filter((line) => line.trim() !== "");
      const headers = lines[0].split(",").map(h => h.trim().toLowerCase());

      const edadIndex = headers.indexOf("edad");
      const sexoIndex = headers.indexOf("sexo");
      const fraseIndex = headers.indexOf("frase");

      if (edadIndex === -1 || sexoIndex === -1 || fraseIndex === -1) {
        alert("❌ El archivo CSV debe tener las columnas: edad, sexo, frase");
        return;
      }

      const data = [];

      for (let i = 1; i < lines.length; i++) {
        const cols = lines[i].split(",");
        if (cols.length < 3) continue;

        data.push({
          edad: cols[edadIndex]?.trim(),
          sexo: cols[sexoIndex]?.trim(),
          frase: cols[fraseIndex]?.trim()
        });
      }

      setCsvData(data);
      setLoteResultados([]);
    };

    reader.readAsText(file);
  };

  const handleClasificarArchivo = async () => {
    if (csvData.length === 0) return;

    setCargando(true);
    setTiempoInicio(Date.now());
    setTiempoFinal(null);

    const resultados = [];

    for (const item of csvData) {
      try {
        const response = await axios.post("http://localhost:5000/clasificar", item);
        resultados.push({
          ...item,
          resultado: response.data.resultado
        });
      } catch (err) {
        resultados.push({
          ...item,
          resultado: "❌ Error en clasificación"
        });
      }
    }

    setLoteResultados(resultados);
    setCargando(false);
    setTiempoFinal(Date.now());
  };

  return (
    <div style={{
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      minHeight: "100vh",
      width: "100vw"
    }}>
      <div style={{
        maxWidth: "500px",
        width: "100%",
        padding: "2rem",
        fontFamily: "sans-serif"
      }}>
        <h1 style={{ textAlign: "center" }}>🧠 Clasificador Emocional</h1>

        {/* FORMULARIO INDIVIDUAL */}
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
          <input
            type="number"
            placeholder="Edad"
            value={edad}
            onChange={(e) => setEdad(e.target.value)}
            required
          />
          <select value={sexo} onChange={(e) => setSexo(e.target.value)}>
            <option value="Masculino">Masculino</option>
            <option value="Femenino">Femenino</option>
          </select>
          <textarea
            placeholder="Escribe aquí la frase..."
            value={frase}
            onChange={(e) => setFrase(e.target.value)}
            rows={4}
            required
          />
          <button type="submit" style={{ padding: "0.5rem", fontWeight: "bold" }}>
            Clasificar
          </button>
        </form>

        <hr style={{ margin: "2rem 0" }} />

        {/* SUBIDA DE CSV */}
        <div style={{ display: "flex", gap: "1rem", justifyContent: "space-between" }}>
          <input
            type="file"
            accept=".csv"
            onChange={handleCSVUpload}
            style={{ marginBottom: "1rem" }}
          />
          {csvData.length > 0 && (
            <button onClick={handleClasificarArchivo} style={{ padding: "0.5rem", fontWeight: "bold", marginBottom: "1rem" }}>
              Clasificar archivo
            </button>
          )}
        </div>

        {cargando && <p style={{ textAlign: "center" }}>🔍 Clasificando...</p>}

        {tiempoInicio && tiempoFinal && (
          <p style={{ textAlign: "center" }}>
            🕒 Tiempo de clasificación: {((tiempoFinal - tiempoInicio) / 1000).toFixed(2)} segundos
          </p>
        )}

        {/* RESULTADO INDIVIDUAL */}
        {resultado && (
          <div style={{ marginTop: "1.5rem", textAlign: "center" }}>
            <h3>📋 Resultado individual:</h3>
            <pre style={{
              backgroundColor: "#1e1e1e",
              padding: "1rem",
              borderRadius: "8px",
              whiteSpace: "pre-wrap",
              wordWrap: "break-word",
              color: "white",
              textAlign: "left",
              fontFamily: "monospace"
            }}>
              {resultado}
            </pre>
          </div>
        )}

        {/* RESULTADOS EN LOTE */}
        {loteResultados.length > 0 && (
          <div style={{ marginTop: "2rem" }}>
            <h3>📑 Resultados del archivo:</h3>
            {loteResultados.map((item, index) => (
              <pre key={index} style={{
                backgroundColor: "#1e1e1e",
                padding: "1rem",
                borderRadius: "8px",
                whiteSpace: "pre-wrap",
                wordWrap: "break-word",
                color: "white",
                textAlign: "left",
                fontFamily: "monospace",
                marginBottom: "1rem"
              }}>
                {`Frase: "${item.frase}"\nClasificación: ${item.resultado}`}
              </pre>
            ))}
          </div>
        )}

        {/* BOTONES DE LIMPIEZA */}
        <div style={{ display: "flex", gap: "1rem", justifyContent: "space-between" }}>
          <button
            type="button"
            onClick={() => {
              setEdad("");
              setSexo("Masculino");
              setFrase("");
              setResultado(null);
              setTiempoInicio(null);
              setTiempoFinal(null);
            }}
            style={{ padding: "0.5rem", fontWeight: "bold" }}
          >
            Limpiar individual
          </button>
          <button
            type="button"
            onClick={() => {
              setCsvData([]);
              setLoteResultados([]);
              setTiempoInicio(null);
              setTiempoFinal(null);
            }}
            style={{ padding: "0.5rem", fontWeight: "bold" }}
          >
            Limpiar archivo
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;
