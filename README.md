# evan-bot

Эван - это бот для автоматизации работы группы по переводу "[Пакта](https://pactwebserial.wordpress.com/)". 
К нему нужно обратиться лично или по имени, иначе он не услышит. Команды слышит без обращения, но возможны варианты,
если на канале есть более одного бота.

## Команды

- `/help` - помощь по командам
- `/export [название или id главы]` - экспорт перевода главы в текстовый файл для выкладки
- `/stats` - статистика перевода
- `/assign` - назначить переводчиков или редакторов
- `/revoke` - убрать из списка переводчиков/редакторов
- `/executives [название или id главы]` - посмотреть список назначенных
- `/clear_executives [название или id главы]` - очистить список назначенных
- "Эван, глава 1.01" - статус главы, ссылка на редактирование если есть

Команды `assign`, `revoke`, `clear_executives` принимаются только от администрации - пользователей, 
указанных в config.py как ADMIN_USERS

Также бот может:

- Помочь в нелегком выборе, если его спросить "Эван, А или Б?"
- Отвечать как ему придет в голову, если он не воспринимает обращение как команду

## Автозамены для выкладки

- `||` - нужен абзац в этом месте перевода
- `<<` - нужно объединить абзацы