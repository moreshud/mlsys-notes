
(function(){
  function disarm(el){
    if(!el) return;
    el.classList.remove('hint');
    el.classList.remove('hint-surface');
  }

  function arm(el){
    function off(){ disarm(el); }
    el.addEventListener('pointerdown', off, {once:true});
    el.addEventListener('keydown', function(e){
      if(e.key==='Enter'||e.key===' '||e.key==='ArrowLeft'||e.key==='ArrowRight'||
         e.key==='ArrowUp'||e.key==='ArrowDown'){ off(); }
    });
    el.addEventListener('input', off, {once:true});
  }

  function init(){
    Array.prototype.forEach.call(
      document.querySelectorAll('.hint, .hint-surface'), arm
    );
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

(function(){
  if(window.parent === window) return;

  document.documentElement.classList.add('ds-embed');

  function post(msg){
    try{ window.parent.postMessage(msg, '*'); }catch(e){}
  }

  function measure(){
    var fig = document.querySelector('.fig');
    var rect = fig ? fig.getBoundingClientRect() : null;
    var h = rect ? Math.ceil(rect.height) + 2 : document.body.scrollHeight;
    var w = rect ? Math.ceil(Math.max(rect.width, fig.scrollWidth)) : document.body.scrollWidth;
    post({type:'ds:height', h:h, w:w});
  }

  window.addEventListener('message', function(e){
    var d = e.data;
    if(!d || typeof d !== 'object') return;
    if(d.type === 'ds:theme' && (d.theme === 'dark' || d.theme === 'light')){
      document.documentElement.setAttribute('data-theme', d.theme);

      if(typeof d.bg === 'string' && d.bg){
        document.documentElement.style.background = d.bg;
        document.body.style.background = d.bg;
      }
      measure();
    }
  });

  function start(){
    post({type:'ds:ready'});
    measure();
    if(window.ResizeObserver){
      var fig = document.querySelector('.fig');
      if(fig) new ResizeObserver(measure).observe(fig);
    }
    window.addEventListener('resize', measure);
    setTimeout(measure, 120);
    setTimeout(measure, 600);
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})();
