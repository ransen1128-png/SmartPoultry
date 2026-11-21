(() => {
    const tooltips=[];
    document.querySelectorAll('[data-bell-tooltip]').forEach(bell => {
        const tooltip=bootstrap.Tooltip.getOrCreateInstance(bell,{trigger:'hover focus',placement:'bottom',container:'body'});
        tooltips.push(tooltip);
        bell.addEventListener('show.bs.dropdown',()=>tooltip.hide());
        bell.addEventListener('click',()=>tooltip.hide());
    });
    window.addEventListener('pagehide',()=>tooltips.forEach(tooltip=>tooltip.hide()));
    const bell=document.getElementById('userNotificationBell');
    if(!bell)return; // Administrator notifications retain their existing dropdown.
    const items=document.getElementById('notificationPreviewItems');
    const status=document.getElementById('notificationPreviewStatus');
    const allLink=document.getElementById('viewAllNotifications');
    let loading=false;
    async function refresh() {
        if(loading || document.hidden)return;
        loading=true;
        try {
            const response=await fetch(bell.dataset.previewUrl,{headers:{Accept:'application/json'},cache:'no-store'});
            if(!response.ok || response.redirected || !response.headers.get('content-type')?.includes('application/json'))throw new Error();
            const data=await response.json();
            if(!Array.isArray(data.results))throw new Error();
            const count=Number(data.unread_count) || 0;
            const badge=document.getElementById('userNotificationCount');badge.textContent=count>99?'99+':String(count);badge.hidden=count===0;
            const menuCount=document.getElementById('notificationPreviewCount');menuCount.textContent=count+' new';menuCount.hidden=count===0;
            items.replaceChildren();
            for(const item of data.results.slice(0,5)) {
                const link=document.createElement('a');link.className='notification-preview-item';link.href=allLink.href+'#notification-'+Number(item.id);link.dataset.unread=String(!item.is_read);
                const icon=document.createElement('span');icon.className='notification-preview-icon';icon.setAttribute('aria-hidden','true');
                const glyph=document.createElement('i');glyph.className='bi bi-bell';icon.append(glyph);
                const copy=document.createElement('span');copy.className='notification-preview-copy';
                const row=document.createElement('span');row.className='notification-preview-row';
                const title=document.createElement('span');title.className='notification-preview-title';title.textContent=item.title;
                const time=document.createElement('time');time.dateTime=item.created_at;time.textContent=item.age;
                const message=document.createElement('span');message.className='notification-preview-message';message.textContent=item.message;
                row.append(title,time);copy.append(row,message);link.append(icon,copy);items.append(link);
            }
            status.hidden=data.results.length>0;status.textContent='No notifications yet.';delete status.dataset.error;
        } catch (_) {
            status.hidden=false;status.dataset.error='true';
            status.textContent=items.children.length?'Unable to refresh. Showing the last loaded notifications.':'Notifications could not load. Use View All Notifications to try the full page.';
        } finally {loading=false;}
    }
    bell.addEventListener('show.bs.dropdown',refresh);
    document.addEventListener('visibilitychange',refresh);
    window.setInterval(refresh,30000);
    refresh();
})();
