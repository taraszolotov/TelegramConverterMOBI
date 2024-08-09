import os
import subprocess
from telegram import Update, InputFile
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackContext
from telegram.error import BadRequest
from pdf2image import convert_from_path

# Отримання токена з середовищних змінних
TOKEN = os.getenv('TOKEN')

# Стани для ConversationHandler
AUTHOR, TITLE, CONVERT = range(3)

# Збереження даних користувача
user_data = {}

def start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text("Привіт! Надішліть мені файл електронної книги, і я перетворю його у формат MOBI.")
    return CONVERT

def handle_document(update: Update, context: CallbackContext) -> int:
    file = update.message.document.get_file()
    file_name = update.message.document.file_name
    user_data['file_name'] = file_name
    file_path = f'/tmp/{file_name}'
    file.download(custom_path=file_path)
    user_data['file_path'] = file_path
    update.message.reply_text('Вкажіть ім\'я автора:')
    return AUTHOR

def ask_title(update: Update, context: CallbackContext) -> int:
    user_data['author'] = update.message.text
    update.message.reply_text('Вкажіть назву книги:')
    return TITLE

def convert_file(update: Update, context: CallbackContext) -> int:
    user_data['title'] = update.message.text
    update.message.reply_text("Конвертую...")

    file_path = user_data['file_path']
    author = user_data.get('author', 'Unknown Author')
    title = user_data.get('title', 'Unknown Title')
    mobi_path = convert_to_mobi(file_path, author, title)
    if mobi_path:
        if mobi_path == "tech_error":
            update.message.reply_text("Стався технічний збій, спробуй пізніше.")
        else:
            try:
                with open(mobi_path, 'rb') as mobi_file:
                    update.message.reply_document(mobi_file, filename=os.path.basename(mobi_path))
            except BadRequest as e:
                if 'File is too big' in str(e):
                    update.message.reply_text("Файл завеликий.")
                else:
                    update.message.reply_text("Пробач, сталася помилка при відправці файлу.")
            os.remove(mobi_path)
    else:
        update.message.reply_text("Пробач, я не зміг конвертувати цей файл.")
    os.remove(file_path)
    return ConversationHandler.END

def convert_to_mobi(input_file: str, author: str, title: str) -> str:
    output_file = input_file.rsplit('.', 1)[0] + '.mobi'
    try:
        # Перший метод конвертації
        subprocess.run(['ebook-convert', input_file, output_file, '--authors', author, '--title', title, '--output-profile', 'kindle'], check=True, timeout=120)
        return output_file
    except subprocess.CalledProcessError:
        try:
            if input_file.endswith('.pdf'):
                # Другий метод конвертації для PDF
                images = convert_from_path(input_file)
                img_files = []
                for i, img in enumerate(images):
                    img_file = f'/tmp/page_{i}.jpg'
                    img.save(img_file, 'JPEG')
                    img_files.append(img_file)
                # Створюємо HTML зображення
                html_file = input_file.rsplit('.', 1)[0] + '.html'
                with open(html_file, 'w') as f:
                    for img_file in img_files:
                        f.write(f'<img src="{img_file}" />\n')
                # Конвертуємо HTML в MOBI
                subprocess.run(['ebook-convert', html_file, output_file, '--authors', author, '--title', title, '--output-profile', 'kindle'], check=True, timeout=120)
                return output_file
        except subprocess.CalledProcessError:
            return None
        except subprocess.TimeoutExpired:
            return "tech_error"
        except Exception:
            return "tech_error"
    except subprocess.TimeoutExpired:
        return "tech_error"
    except Exception:
        return "tech_error"

def main() -> None:
    updater = Updater(TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CONVERT: [MessageHandler(Filters.document, handle_document)],
            AUTHOR: [MessageHandler(Filters.text & ~Filters.command, ask_title)],
            TITLE: [MessageHandler(Filters.text & ~Filters.command, convert_file)],
        },
        fallbacks=[CommandHandler('start', start)],
    )

    dispatcher.add_handler(conv_handler)

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
