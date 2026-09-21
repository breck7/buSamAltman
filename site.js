const search = document.querySelector('#search');
if (search) {
  const rows = [...document.querySelectorAll('.post-row')];
  const groups = [...document.querySelectorAll('.year-group')];
  const status = document.querySelector('#search-status');
  const normalize = text => text.toLocaleLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '');
  const texts = new Map(rows.map(row => [row, normalize(row.querySelector('.post-title').textContent)]));
  function filter() {
    const terms = normalize(search.value.trim()).split(/\s+/).filter(Boolean);
    let count = 0;
    rows.forEach(row => {
      row.hidden = !terms.every(term => texts.get(row).includes(term));
      if (!row.hidden) count++;
    });
    groups.forEach(group => { group.hidden = !group.querySelector('.post-row:not([hidden])'); });
    document.querySelector('#empty').textContent = count === 0 ? 'No essays found. Try another search.' : '';
    status.textContent = search.value ? `${count} ${count === 1 ? 'essay' : 'essays'} found` : '';
  }
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
