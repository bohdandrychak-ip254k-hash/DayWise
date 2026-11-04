const $ = (id) => document.getElementById(id);
let latest = null;
$('day').value = new Date(Date.now() - new Date().getTimezoneOffset() * 60000).toISOString().slice(0,10);
const fmt = (s) => s.slice(11,16);
const escapeHTML = (s) => String(s).replace(/[&<>"']/g, (c) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function render(data) {
  latest = data;
  $('calendarTitle').textContent = new Intl.DateTimeFormat('uk-UA', {day:'numeric',month:'long',weekday:'long'}).format(new Date($('day').value + 'T12:00:00'));
  $('nTasks').textContent = data.scheduled_count;
  $('nHours').textContent = `${Math.floor(data.total_minutes/60)} год ${data.total_minutes%60} хв`;
  $('nLeft').textContent = data.skipped.length;
  $('timeline').innerHTML = data.tasks.length ? data.tasks.map(t => `<div class="entry"><div class="time">${fmt(t.start)}<small>${fmt(t.end)}</small></div><div class="axis"><i class="dot ${t.priority}"></i></div><div class="task"><strong>${escapeHTML(t.title)}</strong><small>${t.duration} хв · ${({'high':'Високий','medium':'Середній','low':'Низький'})[t.priority]} пріоритет</small></div></div>`).join('') : '<div class="empty">На цей день завдання не вмістилися.</div>';
  $('skipped').textContent = data.skipped.length ? 'Не вмістилося: ' + data.skipped.map(t => t.title + ' (' + t.reason + ')').join('; ') : '';
  $('export').disabled = !data.tasks.length;
  setReminders(data.tasks);
}
async function generate() {
  $('error').textContent = '';
  const btn = $('generate'); btn.disabled = true;
  try {
    const response = await fetch('/api/plan', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({description:$('description').value,date:$('day').value,start:$('from').value,end:$('to').value})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Не вдалося сформувати розклад');
    render(result);
  } catch(error) { $('error').textContent = error.message; }
  finally { btn.disabled = false; }
}
$('generate').addEventListener('click', generate);
let reminderTimers = [];
function setReminders(tasks) {
  reminderTimers.forEach(clearTimeout); reminderTimers=[];
  if (!$('remind').checked || !('Notification' in window) || Notification.permission !== 'granted') return;
  for (const t of tasks) {
    const wait = new Date(t.start).getTime() - Date.now() - 5*60000;
    if (wait >= 0 && wait <= 2147483647) reminderTimers.push(setTimeout(() => new Notification('DayWise: скоро завдання', {body:`Через 5 хв: ${t.title}`}),wait));
  }
}
$('remind').addEventListener('change', async() => {
  if ($('remind').checked) {
    if (!('Notification' in window)) { $('error').textContent='Браузер не підтримує сповіщення.'; $('remind').checked=false; return; }
    const permission=await Notification.requestPermission();
    if (permission!=='granted') { $('error').textContent='Дозвіл на сповіщення не надано.'; $('remind').checked=false; return; }
  }
  if(latest) setReminders(latest.tasks);
});
const icsDate = d => d.replace(/[-:]/g,'').replace('T','T')+'00';
const icsEscape = s => s.replace(/\\/g,'\\\\').replace(/\n/g,'\\n').replace(/,/g,'\\,').replace(/;/g,'\\;');
$('export').addEventListener('click', () => {
  if(!latest) return;
  const lines = ['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//DayWise//UA','CALSCALE:GREGORIAN'];
  latest.tasks.forEach((t,i) => lines.push('BEGIN:VEVENT',`UID:daywise-${Date.now()}-${i}@local`,`DTSTAMP:${new Date().toISOString().replace(/[-:]/g,'').replace(/\.\d{3}/,'')}`,`DTSTART:${icsDate(t.start)}`,`DTEND:${icsDate(t.end)}`,`SUMMARY:${icsEscape(t.title)}`,'END:VEVENT'));
  lines.push('END:VCALENDAR');
  const blob = new Blob([lines.join('\r\n')],{type:'text/calendar;charset=utf-8'});
  const url=URL.createObjectURL(blob), a=document.createElement('a');a.href=url;a.download='daywise-plan.ics';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
