with open('telegram_bot.py', 'r', encoding='utf-8') as f:
    content = f.read()

target = '    # Tampilkan indikasi "typing..."\n    await context.bot.send_chat_action(chat_id=chat_id, action="typing")\n\n    try:'

replacement = '''    # Tampilkan indikasi "typing..."
    async def keep_typing():
        try:
            while True:
                await context.bot.send_chat_action(chat_id=chat_id, action="typing")
                await asyncio.sleep(4.5)
        except asyncio.CancelledError:
            pass

    typing_task = asyncio.create_task(keep_typing())

    try:'''

if target in content:
    content = content.replace(target, replacement, 1)
    with open('telegram_bot.py', 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    print("SUCCESS")
else:
    # Try with CRLF
    target_crlf = target.replace('\n', '\r\n')
    if target_crlf in content:
        content = content.replace(target_crlf, replacement.replace('\n', '\r\n'), 1)
        with open('telegram_bot.py', 'w', encoding='utf-8') as f:
            f.write(content)
        print("SUCCESS CRLF")
    else:
        print("NOT FOUND")
