const search = document.querySelector('#search');
if (search) {
  const rows = [...document.querySelectorAll('.post-row')];
  const groups = [...document.querySelectorAll('.year-group')];
  const status = document.querySelector('#search-status');
  const buttons = [...document.querySelectorAll('[data-sort]')];
  const archive = document.querySelector('.archive');
  const sortedList = document.createElement('div');
  sortedList.className = 'sorted-posts';
  sortedList.hidden = true;
  groups[0]?.before(sortedList);
  const metadata = new Map(rows.map((row, index) => {
    const time = row.querySelector('time');
    const year = row.closest('.year-group').dataset.year;
    return [row, { parent: row.parentElement, index, date: time.dateTime,
      undated: year === 'Undated', duration: parseFloat(row.querySelector('.read-time').textContent),
      shortDate: time.textContent, fullDate: year === 'Undated' ? 'Undated' : `${time.textContent} ${year}`.trim() }];
  }));
  let sortKey = 'date';
  let direction = -1;
  let sortChanged = false;
  const normalize = text => text.toLocaleLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '');
  const texts = new Map(rows.map(row => [row, normalize(row.querySelector('.post-title').textContent)]));
  function filter() {
    const terms = normalize(search.value.trim()).split(/\s+/).filter(Boolean);
    let count = 0;
    rows.forEach(row => {
      row.hidden = !terms.every(term => texts.get(row).includes(term));
      if (!row.hidden) count++;
    });
    groups.forEach(group => { group.hidden = sortKey !== 'date' || !group.querySelector('.post-row:not([hidden])'); });
    document.querySelector('#empty').textContent = count === 0 ? 'No essays found. Try another search.' : '';
    const order = sortKey === 'date' ? (direction < 0 ? 'newest first' : 'oldest first') : (direction > 0 ? 'shortest first' : 'longest first');
    status.textContent = search.value || sortChanged ? `${count} ${count === 1 ? 'essay' : 'essays'} · ${order}` : '';
  }
  function sort(key) {
    direction = key === sortKey ? -direction : key === 'date' ? -1 : 1;
    sortKey = key;
    sortChanged = true;
    const ordered = [...rows].sort((a, b) => {
      const x = metadata.get(a), y = metadata.get(b);
      if (key === 'date' && x.undated !== y.undated) return x.undated ? 1 : -1;
      const result = key === 'date' ? x.date.localeCompare(y.date) : x.duration - y.duration;
      return result * direction || x.index - y.index;
    });
    archive.classList.toggle('duration-order', key === 'duration');
    sortedList.hidden = key !== 'duration';
    ordered.forEach(row => {
      const meta = metadata.get(row);
      (key === 'duration' ? sortedList : meta.parent).append(row);
      row.querySelector('time').textContent = key === 'duration' ? meta.fullDate : meta.shortDate;
    });
    if (key === 'date') {
      [...groups].sort((a, b) => {
        if (a.dataset.year === 'Undated') return 1;
        if (b.dataset.year === 'Undated') return -1;
        return (Number(a.dataset.year) - Number(b.dataset.year)) * direction;
      }).forEach(group => sortedList.before(group));
    }
    buttons.forEach(button => {
      const active = button.dataset.sort === key;
      const label = button.dataset.sort === 'date' ? 'Date' : 'Duration';
      button.textContent = `${label} ${active ? (direction > 0 ? '↑' : '↓') : '↕'}`;
      button.setAttribute('aria-label', `Sort by ${label.toLowerCase()}, ${button.dataset.sort === 'date' ? (active && direction < 0 ? 'oldest' : 'newest') : (active && direction > 0 ? 'longest' : 'shortest')} first`);
    });
    filter();
  }
  buttons.forEach(button => button.addEventListener('click', () => sort(button.dataset.sort)));
  search.addEventListener('input', filter);
  document.addEventListener('keydown', event => {
    if (event.key === '/' && !/INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName)) {
      event.preventDefault(); search.focus();
    }
    if (event.key === 'Escape' && document.activeElement === search) {
      search.value = ''; filter(); search.blur();
    }
  });
}