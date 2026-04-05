import asyncio
import logging
import uuid
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, FSInputFile
from aiogram.client.default import DefaultBotProperties
from PIL import Image, ImageOps
import pytesseract

from statistik import BOT_TOKEN, ADMIN_ID, OCR_LANGS


# =========================
# TEKSHIRUV
# =========================
if not BOT_TOKEN or BOT_TOKEN == "BU_YERGA_BOT_TOKENINGIZNI_YOZING":
    raise ValueError("statistik.py ichiga to'g'ri BOT_TOKEN yozilmagan.")


# Agar Windows'da Tesseract alohida o'rnatilgan bo'lsa,
# kerak bo'lsa pastdagi qatorni ochib yo'lini yozasiz:
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# =========================
# PAPKALAR
# =========================
BASE_DIR = Path(__file__).resolve().parent
TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True)


# =========================
# LOG
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("ocr_bot")


# =========================
# BOT
# =========================
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()


# =========================
# YORDAMCHI FUNKSIYALAR
# =========================
def build_temp_file(ext: str) -> Path:
    return TEMP_DIR / f"{uuid.uuid4().hex}{ext}"


def cleanup_file(file_path: Path) -> None:
    try:
        if file_path.exists():
            file_path.unlink()
    except Exception as e:
        logger.warning(f"Faylni o'chirishda xato: {e}")


def preprocess_image(image_path: Path) -> Image.Image:
    image = Image.open(image_path)
    image = ImageOps.exif_transpose(image)   # rasm aylangan bo'lsa tuzatadi
    image = image.convert("L")               # oq-qora/grayscale
    image = image.point(lambda x: 0 if x < 140 else 255, "1")
    return image


def extract_text_from_image(image_path: Path) -> str:
    processed_image = preprocess_image(image_path)
    config = r"--oem 3 --psm 6"
    text = pytesseract.image_to_string(
        processed_image,
        lang=OCR_LANGS,
        config=config
    )
    return text.strip()


def save_text_to_txt(text: str) -> Path:
    txt_file = build_temp_file(".txt")
    txt_file.write_text(text, encoding="utf-8")
    return txt_file


def split_long_text(text: str, limit: int = 3900) -> list[str]:
    if len(text) <= limit:
        return [text]

    parts = []
    current = ""

    for line in text.splitlines():
        if len(current) + len(line) + 1 <= limit:
            current += line + "\n"
        else:
            if current.strip():
                parts.append(current.strip())
            current = line + "\n"

    if current.strip():
        parts.append(current.strip())

    return parts


async def send_admin_message(text: str) -> None:
    try:
        if ADMIN_ID:
            await bot.send_message(ADMIN_ID, text)
    except Exception as e:
        logger.warning(f"Adminga xabar yuborilmadi: {e}")


# =========================
# BUYRUQLAR
# =========================
@dp.message(CommandStart())
async def start_handler(message: Message):
    text = (
        "<b>Assalomu alaykum.</b>\n\n"
        "Men rasm ichidagi yozuvni matnga aylantiruvchi botman.\n\n"
        "<b>Imkoniyatlar:</b>\n"
        "• rasm ichidan text ajratish\n"
        "• natijani chatga yuborish\n"
        "• natijani .txt fayl ko'rinishida yuborish\n\n"
        "Rasm yuboring."
    )
    await message.answer(text)


@dp.message(Command("help"))
async def help_handler(message: Message):
    text = (
        "<b>Foydalanish:</b>\n"
        "1. Botga rasm yuboring\n"
        "2. Men yozuvlarni o'qib olaman\n"
        "3. Natijani text va txt fayl qilib yuboraman\n\n"
        f"<b>OCR tillari:</b> <code>{OCR_LANGS}</code>"
    )
    await message.answer(text)


@dp.message(Command("id"))
async def id_handler(message: Message):
    await message.answer(f"Sizning ID: <code>{message.from_user.id}</code>")


# =========================
# PHOTO HANDLER
# =========================
@dp.message(F.photo)
async def photo_handler(message: Message):
    status_msg = await message.answer("Rasm qabul qilindi. Text ajratilyapti...")

    image_path = None
    txt_path = None

    try:
        photo = message.photo[-1]
        image_path = build_temp_file(".jpg")
        await bot.download(photo, destination=image_path)

        text = extract_text_from_image(image_path)

        if not text:
            await status_msg.edit_text(
                "Rasm ichida o'qiladigan text topilmadi.\n"
                "Aniqroq rasm yuborib ko'ring."
            )
            return

        parts = split_long_text(text)

        await status_msg.edit_text("Text topildi. Yuborilyapti...")

        for i, part in enumerate(parts, start=1):
            if len(parts) == 1:
                await message.answer(f"<b>Ajratilgan text:</b>\n\n<pre>{part}</pre>")
            else:
                await message.answer(
                    f"<b>Ajratilgan text ({i}/{len(parts)}):</b>\n\n<pre>{part}</pre>"
                )

        txt_path = save_text_to_txt(text)
        await message.answer_document(
            FSInputFile(txt_path),
            caption="OCR natijasi txt fayl ko'rinishida."
        )

        await status_msg.delete()

    except Exception as e:
        logger.exception(f"Photo handler xatoligi: {e}")
        await status_msg.edit_text("Xatolik yuz berdi.")
        await send_admin_message(f"Photo OCR xatoligi:\n{e}")

    finally:
        if image_path:
            cleanup_file(image_path)
        if txt_path:
            cleanup_file(txt_path)


# =========================
# DOCUMENT HANDLER
# =========================
@dp.message(F.document)
async def document_handler(message: Message):
    doc = message.document

    if not doc:
        return

    mime_type = doc.mime_type or ""
    file_name = (doc.file_name or "").lower()

    is_image = (
        mime_type.startswith("image/")
        or file_name.endswith(".jpg")
        or file_name.endswith(".jpeg")
        or file_name.endswith(".png")
        or file_name.endswith(".webp")
        or file_name.endswith(".bmp")
    )

    if not is_image:
        await message.answer(
            "Hozircha faqat rasm fayllar qabul qilinadi.\n"
            "Masalan: JPG, PNG, WEBP, BMP."
        )
        return

    status_msg = await message.answer("Fayl qabul qilindi. Text ajratilyapti...")

    image_path = None
    txt_path = None

    try:
        suffix = Path(doc.file_name).suffix if doc.file_name else ".jpg"
        if not suffix:
            suffix = ".jpg"

        image_path = build_temp_file(suffix)
        await bot.download(doc, destination=image_path)

        text = extract_text_from_image(image_path)

        if not text:
            await status_msg.edit_text(
                "Fayl ichida o'qiladigan text topilmadi.\n"
                "Aniqroq rasm yuborib ko'ring."
            )
            return

        parts = split_long_text(text)

        await status_msg.edit_text("Text topildi. Yuborilyapti...")

        for i, part in enumerate(parts, start=1):
            if len(parts) == 1:
                await message.answer(f"<b>Ajratilgan text:</b>\n\n<pre>{part}</pre>")
            else:
                await message.answer(
                    f"<b>Ajratilgan text ({i}/{len(parts)}):</b>\n\n<pre>{part}</pre>"
                )

        txt_path = save_text_to_txt(text)
        await message.answer_document(
            FSInputFile(txt_path),
            caption="OCR natijasi txt fayl ko'rinishida."
        )

        await status_msg.delete()

    except Exception as e:
        logger.exception(f"Document handler xatoligi: {e}")
        await status_msg.edit_text("Xatolik yuz berdi.")
        await send_admin_message(f"Document OCR xatoligi:\n{e}")

    finally:
        if image_path:
            cleanup_file(image_path)
        if txt_path:
            cleanup_file(txt_path)


# =========================
# FALLBACK
# =========================
@dp.message()
async def fallback_handler(message: Message):
    await message.answer(
        "Menga rasm yuboring, men uni text ko'rinishiga o'tkazaman.\n"
        "Buyruqlar: /start /help /id"
    )


# =========================
# MAIN
# =========================
async def main():
    me = await bot.get_me()
    logger.info(f"Bot ishga tushdi: @{me.username}")
    await send_admin_message(f"OCR bot ishga tushdi: @{me.username}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot to'xtatildi.")
