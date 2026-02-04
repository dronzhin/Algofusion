import os
import json

# Имя файла для хранения данных
filename = 'ex.json'

# Создание файла, если его нет
if not os.path.exists(filename):
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump({}, f, ensure_ascii=False, indent=2)
    print(f"Файл {filename} создан.")

# Загрузка данных из файла
with open(filename, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Словарь соответствия типа документа ключу в JSON
doc_types = {
    "1": ("Товарная накладная", "packing_list"),
    "2": ("Счет", "invoice"),
    "3": ("Платежное поручение", "payment_order"),
    "4": ("Счет протокол", "account_protocol")
}

def get_doc_type():
    while True:
        print("\nВыберите тип документа:")
        for key, value in doc_types.items():
            print(f"{key}. {value[0]}")
        choice = input("Введите номер: ").strip()
        if choice in doc_types:
            return doc_types[choice][1]
        else:
            print("Неверный выбор, попробуйте снова.")

def ask_yes_no(prompt):
    while True:
        answer = input(prompt).strip()
        if answer == '1':
            return True
        elif answer == '0':
            return False
        else:
            print("Неверный формат. Введите 1 для 'да' или 0 для 'нет'.")

def get_non_empty_input(prompt):
    while True:
        value = input(prompt).strip()
        if value:
            return value
        else:
            print("Это поле не может быть пустым. Попробуйте снова.")

def collect_packing_list_or_invoice():
    doc_data = {}
    doc_data["invoice_number"] = get_non_empty_input("Введите номер накладной/счета: ")
    doc_data["invoice_date"] = get_non_empty_input("Введите дату (например, 23.08.2024): ")
    items = []
    line_num = 1
    while True:
        item = {}
        item["line_number"] = line_num
        item["description"] = get_non_empty_input(f"Введите описание товара #{line_num}: ")
        item["unit"] = get_non_empty_input("Введите единицу измерения (например, шт): ")
        items.append(item)
        line_num += 1
        if not ask_yes_no("Добавить ещё один товар? (1 — да, 0 — нет): "):
            break
    doc_data["items"] = items
    return doc_data

def collect_payment_order():
    doc_data = {}
    doc_data["payment_order_number"] = get_non_empty_input("Введите номер платежного поручения: ")
    doc_data["payment_order_type"] = get_non_empty_input("Введите тип (например, сокращённое): ")
    doc_data["document_date"] = get_non_empty_input("Введите дату документа (например, 13.11.2024): ")
    return doc_data

def collect_account_protocol():
    doc_data = {}
    doc_data["document_number"] = get_non_empty_input("Введите номер документа: ")
    doc_data["document_date"] = get_non_empty_input("Введите дату документа (например, 13.06.2024): ")
    doc_data["valid_until"] = get_non_empty_input("Введите срок действия (например, 18.06.2024): ")
    return doc_data

def main_loop():
    while True:
        doc_key = get_doc_type()
        file_name = get_non_empty_input("Введите название файла (используется как ключ): ")

        # Проверяем, существует ли уже такой файл в типе документа
        if doc_key not in data:
            data[doc_key] = {}

        if file_name in data[doc_key]:
            if ask_yes_no(f"Файл '{file_name}' уже существует. Хотите перезаписать? (1 — да, 0 — нет): "):
                pass  # Продолжить и перезаписать
            else:
                continue  # Перейти к следующей итерации

        # Сбор данных в зависимости от типа
        if doc_key in ["packing_list", "invoice"]:
            doc_data = collect_packing_list_or_invoice()
        elif doc_key == "payment_order":
            doc_data = collect_payment_order()
        elif doc_key == "account_protocol":
            doc_data = collect_account_protocol()

        # Сохраняем в JSON
        data[doc_key][file_name] = doc_data

        # Сохраняем в файл
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"Данные для '{file_name}' сохранены в {filename}")

        if not ask_yes_no("Хотите внести данные для другого файла? (1 — да, 0 — нет): "):
            break

if __name__ == "__main__":
    main_loop()
    print("Программа завершена.")