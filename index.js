const express = require('express');
const app = express();

app.get('/connect/:code', (req, res) => {
  const code = req.params.code;
  res.redirect(302, `http://31.130.131.214/sub/${code}`);
});

// Для проверки — главная страница
app.get('/', (req, res) => {
  res.send('Redirect server работает! Используй /connect/твой_sub_id');
});

const port = process.env.PORT || 3000;
app.listen(port, '0.0.0.0', () => {
  console.log(`Сервер на порту ${port}`);
});
