import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telebot.handler_backends import State, StatesGroup
from telebot.storage import StateMemoryStorage
import logging

# Налаштування логування
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Токен бота
TOKEN = '7784091701:AAHaJiDcL2mEzLXWd-NkQF-L3Ror0ks8GoY'
# Список ID адміністраторів
ADMIN_CHAT_IDS = [1054730072]  # Замініть на реальні ID
bot = telebot.TeleBot(TOKEN, state_storage=StateMemoryStorage())


# Визначення станів
class UserState(StatesGroup):
    waiting_for_message = State()  # Стан для очікування повідомлень користувача


# Функція для створення inline-клавіатури головного меню
def create_inline_keyboard():
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(
        InlineKeyboardButton('Надіслати повідомлення про випадки корупції', callback_data='corruption'),
        InlineKeyboardButton('Надіслати звернення з метою роз’яснення питання', callback_data='inquiry'),
        InlineKeyboardButton('Надіслати скаргу на дії адміністрації', callback_data='complaint'),
        InlineKeyboardButton('Відповідь на найпопулярніші запитання', callback_data='faq'),
        InlineKeyboardButton('Інформація про адреси установ південного регіону', callback_data='locations'),
        InlineKeyboardButton('Контактна інформація Південно-Центрального МРУ', callback_data='contacts')
    )
    return markup


# Обробник команди /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    logging.info(f"Отримано /start від користувача {message.from_user.id}")
    welcome_text = "Вас вітає телеграм бот Південно-Центрального міжрегіонального управління з питань виконання кримінальних покарань Міністерства юстиції, чим можу Вам допомогти?"
    bot.send_message(message.chat.id, welcome_text, reply_markup=create_inline_keyboard())


# Обробник натискань на inline-кнопки
@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    logging.info(f"Отримано callback: {call.data} від користувача {call.from_user.id}")
    bot.answer_callback_query(call.id)
    if call.data in ['corruption', 'inquiry', 'complaint']:
        with bot.retrieve_data(call.from_user.id, call.message.chat.id) as data:
            data['message_type'] = call.data
        bot.set_state(call.from_user.id, UserState.waiting_for_message, call.message.chat.id)
        logging.info(f"Встановлено стан для користувача {call.from_user.id}: {call.data}")

        if call.data == 'corruption':
            bot.send_message(call.message.chat.id,
                             "Будь ласка, опишіть випадок корупції. Ваше повідомлення буде надіслано адміністратору.")
        elif call.data == 'inquiry':
            bot.send_message(call.message.chat.id,
                             "Будь ласка, опишіть ваше питання для роз’яснення. Ваше повідомлення буде надіслано адміністратору.")
        elif call.data == 'complaint':
            bot.send_message(call.message.chat.id,
                             "Будь ласка, опишіть скаргу на дії адміністрації. Ваше повідомлення буде надіслано адміністратору.")

    elif call.data == 'faq':
        bot.send_message(call.message.chat.id, "Ось відповіді на найпопулярніші запитання: [додайте FAQ тут].")
    elif call.data == 'locations':
        bot.send_message(call.message.chat.id, "Інформація про установи: [додайте адреси та контакти тут].")
    elif call.data == 'contacts':
        bot.send_message(call.message.chat.id, "Контактна інформація: [додайте контакти тут].")


# Обробник повідомлень від користувача в стані очікування
@bot.message_handler(state=UserState.waiting_for_message)
def handle_user_message(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    username = message.from_user.username or "Невідомий"

    with bot.retrieve_data(user_id, chat_id) as data:
        message_type = data.get('message_type', 'Невідомий тип')

    logging.info(
        f"Отримано повідомлення від користувача {user_id} (@{username}), тип: {message_type}, текст: {message.text}")

    for admin_id in ADMIN_CHAT_IDS:
        try:
            # Пересилаємо повідомлення кожному адміністратору
            forwarded = bot.forward_message(admin_id, chat_id, message.message_id)
            bot.send_message(admin_id, f"Тип запиту: {message_type} від @{username} (ID: {user_id})",
                             reply_to_message_id=forwarded.message_id)
            logging.info(f"Повідомлення переслано адміністратору {admin_id}")
        except Exception as e:
            logging.error(f"Помилка при надсиланні адміністратору {admin_id}: {str(e)}")
            if "chat not found" in str(e).lower():
                logging.error(f"Адміністратор {admin_id} не взаємодіяв з ботом. Потрібно надіслати /start.")

    bot.reply_to(message,
                 "Ваше повідомлення надіслано адміністратору.")


# Обробник відповідей адміністратора через reply
@bot.message_handler(func=lambda message: message.chat.id in ADMIN_CHAT_IDS and message.reply_to_message is not None)
def handle_admin_reply(message):
    logging.info(f"Отримано відповідь від адміністратора {message.chat.id}")
    if message.reply_to_message.forward_from:
        user_id = message.reply_to_message.forward_from.id
        try:
            bot.send_message(user_id, message.text)  # Надсилаємо текст користувачу
            bot.reply_to(message, "Відповідь надіслано користувачу.")
            logging.info(f"Відповідь адміністратора {message.chat.id} надіслано користувачу {user_id}: {message.text}")
            for admin_id in ADMIN_CHAT_IDS:
                if admin_id != message.chat.id:
                    try:
                        bot.send_message(admin_id,
                                         f"Адміністратор {message.chat.id} відповів користувачу ID: {user_id}: {message.text}")
                    except Exception as e:
                        logging.error(f"Помилка при сповіщенні адміністратора {admin_id}: {str(e)}")
        except Exception as e:
            logging.error(f"Помилка при надсиланні користувачу {user_id}: {str(e)}")
            bot.reply_to(message, f"Помилка при надсиланні відповіді: {str(e)}")
    else:
        bot.reply_to(message, "Це не відповідь на переслане повідомлення від користувача.")
        logging.warning(f"Адміністратор {message.chat.id} відповів не на переслане повідомлення")


# Обробник інших повідомлень
@bot.message_handler(func=lambda message: True)
def handle_other(message):
    if bot.get_state(message.from_user.id, message.chat.id) is None:
        bot.reply_to(message, "Будь ласка, оберіть опцію з меню або почніть з /start.")
        logging.info(f"Отримано неочікуване повідомлення від {message.from_user.id}")
    else:
        handle_user_message(message)


# Запуск бота
if __name__ == '__main__':
    logging.info("Бот запущено")
    bot.infinity_polling()