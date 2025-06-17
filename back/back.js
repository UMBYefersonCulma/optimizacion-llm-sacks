const express = require('express');
const cors = require('cors');
const bodyParser = require('body-parser');
const { spawn } = require('child_process');

const app = express();
const PORT = 5000;

app.use(cors());
app.use(bodyParser.json());

app.post('/clasificar', async (req, res) => {
  const { edad, sexo, frase } = req.body;

  const entrada = `Frase: "${frase}"\nEdad: ${edad}\nSexo: ${sexo}`;

  const ollama = spawn('ollama', ['run', 'practicas'], {
    stdio: ['pipe', 'pipe', 'inherit'],
  });

  let output = '';
  ollama.stdout.on('data', (data) => {
    output += data.toString();
  });

  ollama.stdin.write(entrada + '\n');
  ollama.stdin.end();

  ollama.on('close', (code) => {
    if (code !== 0) {
      return res.status(500).json({ error: 'Error al ejecutar el modelo personalizado' });
    }

    res.json({ resultado: output.trim() });
  });
});

app.listen(PORT, () => {
  console.log(`✅ Backend corriendo en http://localhost:${PORT}`);
});
