import tkinter as tk
from tkinter import ttk
import sqlite3
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.animation import FuncAnimation
from datetime import datetime
import threading
import serial


# Глобальные переменные для данных
humidity_data = []
temperature_data = []
ec_data = []
timestamps = []
current_dev_id = 18  # Текущий ID устройства


# ЧТЕНИЕ КОМ-ПОРТА И ПАРСИНГ
def read_com_port():
    ser = serial.Serial('COM12', baudrate=115200, timeout=1)
    try:
        while True:
            if ser.in_waiting > 0:
                pre_data = ser.readline().decode('utf-8').strip()
                data = parse_data_from(pre_data)
                add_inf_db(data)
                get_last_15_from_db(current_dev_id)  # Обновляем для текущего dev_id
    except KeyboardInterrupt:
        print("Программа завершена")
    finally:
        ser.close()


def parse_data_from(data):
    pre_parts = data.split(': ')
    if len(pre_parts) > 1:
        parts = pre_parts[1].split(' ')
        if len(parts) >= 4:
            return parts
    return []


# Работа с базой данных
def create_data_base():
    connection = sqlite3.connect("sensor_data")
    cursor = connection.cursor()
    cursor.execute(''' 
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dev_id INTEGER,
            humidity REAL,
            temperature REAL,
            ec REAL,
            timestamp TEXT
        )
    ''')
    connection.commit()
    connection.close()


def add_inf_db(data):
    if len(data) < 4:
        print("Недостаточно данных для записи в базу:", data)
        return

    connection = sqlite3.connect("sensor_data")
    cursor = connection.cursor()
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            "INSERT INTO sensor_data(dev_id, humidity, temperature, ec, timestamp) VALUES (?, ?, ?, ?, ?)",
            (int(data[0]), float(data[1]), float(data[2]), float(data[3]), timestamp)
        )
        connection.commit()
    except ValueError as e:
        print("Ошибка в данных:", e, data)
    finally:
        connection.close()


def get_last_15_from_db(dev_id):
    """
    Возвращает последние 15 записей из базы данных для указанного dev_id.
    """
    global humidity_data, temperature_data, ec_data, timestamps
    connection = sqlite3.connect("sensor_data")
    cursor = connection.cursor()
    cursor.execute("""
        SELECT humidity, temperature, ec, timestamp
        FROM sensor_data
        WHERE dev_id = ?
        ORDER BY id DESC
        LIMIT 15
    """, (dev_id,))
    rows = cursor.fetchall()
    connection.close()

    # Обновление глобальных переменных
    humidity_data.clear()
    temperature_data.clear()
    ec_data.clear()
    timestamps.clear()
    for row in reversed(rows):
        humidity_data.append(row[0])
        temperature_data.append(row[1])
        ec_data.append(row[2])
        timestamps.append(row[3])

    return rows  # Возвращаем данные для использования


def get_all_device_ids():
    connection = sqlite3.connect("sensor_data")
    cursor = connection.cursor()
    cursor.execute("SELECT DISTINCT dev_id FROM sensor_data")
    device_ids = [row[0] for row in cursor.fetchall()]
    connection.close()
    return device_ids


# Класс приложения
class MyApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sensor Data App")
        self.root.geometry("1200x800")

        # Создаем вкладки
        self.tabs = ttk.Notebook(root)
        self.tabs.pack(fill=tk.BOTH, expand=True)

        # Вкладка с графиками
        self.graphs_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.graphs_tab, text="Graphs")
        self.setup_graphs_tab()

        # Вкладка с таблицей
        self.database_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.database_tab, text="Database")
        self.setup_database_tab()

    def setup_graphs_tab(self):
        """
        Настройка вкладки Graphs, включая графики и выбор устройства.
        """
        frame = ttk.Frame(self.graphs_tab)
        frame.pack(fill=tk.BOTH, expand=True)

        # Создание области для графиков
        self.figure, self.axes = plt.subplots(2, 2, figsize=(10, 6))
        self.canvas = FigureCanvasTkAgg(self.figure, master=frame)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Выпадающий список для выбора устройства
        device_ids = get_all_device_ids()
        self.device_combo = ttk.Combobox(frame, values=list(map(str, device_ids)))
        self.device_combo.set(str(current_dev_id))  # Установить текущий dev_id как выбранный
        self.device_combo.bind("<<ComboboxSelected>>", self.update_graphs)
        self.device_combo.pack(side=tk.TOP, pady=10)

        # Настройка анимации графиков
        self.animation = FuncAnimation(self.figure, self.animate, interval=1000)

    def setup_database_tab(self):
        """
        Настройка вкладки Database с таблицей и кнопками.
        """
        frame = ttk.Frame(self.database_tab)
        frame.pack(fill=tk.BOTH, expand=True)

        # Таблица для отображения данных
        self.table = ttk.Treeview(frame, columns=("Device ID", "Humidity", "Temperature", "EC", "Timestamp"),
                                  show="headings", height=20)
        self.table.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # Настройка заголовков таблицы
        for col in ("Device ID", "Humidity", "Temperature", "EC", "Timestamp"):
            self.table.heading(col, text=col)
            self.table.column(col, width=100)

        # Кнопка для обновления таблицы
        update_button = ttk.Button(frame, text="Update Data", command=self.load_database)
        update_button.pack(side=tk.LEFT, padx=10, pady=10)

        # Кнопка для очистки базы данных
        clear_button = ttk.Button(frame, text="Clear Database", command=self.clear_database)
        clear_button.pack(side=tk.RIGHT, padx=10, pady=10)

        # Загрузка данных в таблицу
        self.load_database()

    def load_database(self):

        self.table.delete(*self.table.get_children())
        data = get_last_15_from_db(current_dev_id)  # Теперь данные возвращаются
        for row in data:
            self.table.insert("", tk.END, values=row)

    def clear_database(self):
        """
        Очищает базу данных.
        """
        connection = sqlite3.connect("sensor_data")
        cursor = connection.cursor()
        cursor.execute("DELETE FROM sensor_data")
        connection.commit()
        connection.close()
        self.load_database()

    def update_graphs(self, event=None):
        """
        Обновляет графики на вкладке Graphs при изменении выбранного устройства.
        """
        global current_dev_id
        current_dev_id = int(self.device_combo.get())  # Получаем выбранный dev_id
        get_last_15_from_db(current_dev_id)  # Получаем последние 15 данных для устройства
        self.animate(0)  # Перерисовываем графики

    def animate(self, i):
        """
        Анимация для графиков.
        """
        if len(humidity_data) > 0:
            for ax in self.axes.flatten():
                ax.clear()

            self.axes[0, 0].plot(timestamps, humidity_data, label="Humidity", marker='o')
            self.axes[0, 0].set_title("Humidity")
            self.axes[0, 0].set_ylabel("Humidity (%)")
            self.axes[0, 0].grid(True)

            self.axes[0, 1].plot(timestamps, temperature_data, label="Temperature", marker='x')
            self.axes[0, 1].set_title("Temperature")
            self.axes[0, 1].set_ylabel("Temperature (°C)")
            self.axes[0, 1].grid(True)

            self.axes[1, 0].plot(timestamps, ec_data, label="EC", marker='s')
            self.axes[1, 0].set_title("EC")
            self.axes[1, 0].set_ylabel("EC (µS/cm)")
            self.axes[1, 0].grid(True)

            self.axes[1, 1].axis('off')
            self.canvas.draw()


if __name__ == "__main__":
    create_data_base()
    root = tk.Tk()
    app = MyApp(root)

    # Запуск потока для чтения данных с COM-порта
    thread = threading.Thread(target=read_com_port, daemon=True)
    thread.start()

    root.mainloop()
