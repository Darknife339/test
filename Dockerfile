# Используем легковесный образ Python
FROM python:3.10-slim

# Устанавливаем системные зависимости для работы с сетью и сертификатами
RUN apt-get update && apt-get install -y \
    ca-certificates \
    curl \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Создаем рабочую директорию внутри контейнера
WORKDIR /code

# Копируем список библиотек и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем основной код бота
COPY . .

# Render будет использовать этот порт для проверки работоспособности (Health Check)
EXPOSE 7860

# Команда для запуска бота
CMD ["python", "main.py"]
