(() => {
    const popovers=[];
    document.querySelectorAll('[data-record-help]').forEach(button => {
        const content=document.getElementById(button.dataset.recordHelp);
        if(!content)return;
        popovers.push(bootstrap.Popover.getOrCreateInstance(button,{
            title:button.dataset.helpTitle,content:()=>content.innerHTML,
            html:true,sanitize:true,trigger:'hover focus',placement:'top',container:'body',customClass:'record-help-popover',
        }));
    });
    document.addEventListener('keydown',event=>{if(event.key==='Escape')popovers.forEach(popover=>popover.hide());});
    window.addEventListener('pagehide',()=>popovers.forEach(popover=>popover.hide()));
})();
