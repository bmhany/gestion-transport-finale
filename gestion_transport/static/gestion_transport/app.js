const ADMIN_PASS = '97654';

let S = {
    role: '', uid: '', view: '',
    dark: localStorage.getItem('mc_dark') === '1',
    data: {
        lines: JSON.parse(localStorage.getItem('mc_lines')) || [
            {name: 'Ligne 1 - Cité ↔ Fac', status: 'active', nextTime: '08:30', station: 'Cité Universitaire'},
            {name: 'Ligne 2 - Tramway ↔ Résidences', status: 'inactive', nextTime: '10:00', station: 'Arrêt Tramway'}
        ],
        stations: JSON.parse(localStorage.getItem('mc_stations')) || ['Cité Universitaire', 'Faculté Centrale', 'Arrêt Tramway'],
        buses: JSON.parse(localStorage.getItem('mc_buses')) || [
            {name: 'Bus 01', capacity: 50, reserved: 0, line: 'Ligne 1 - Cité ↔ Fac', time: '08:30'},
            {name: 'Bus 02', capacity: 30, reserved: 0, line: 'Ligne 2 - Tramway ↔ Résidences', time: '10:00'}
        ],
        drivers: JSON.parse(localStorage.getItem('mc_drivers')) || [
            {id: 'DRV-001', name: 'Ahmed Mansouri', line: 'Ligne 1 - Cité ↔ Fac', time: '08:30', station: 'Cité Universitaire'},
            {id: 'DRV-002', name: 'Yacine Benali', line: 'Ligne 2 - Tramway ↔ Résidences', time: '10:00', station: 'Arrêt Tramway'}
        ],
        incidents: JSON.parse(localStorage.getItem('mc_incidents')) || [],
        reservations: JSON.parse(localStorage.getItem('mc_reservations')) || [],
        notifications: JSON.parse(localStorage.getItem('mc_notifications')) || []
    }
};

function save(k){ localStorage.setItem('mc_'+k, JSON.stringify(S.data[k])); }

// Chargement instantané - suppression de l'écran de chargement

// Attacher les event listeners quand le DOM est prêt
document.addEventListener('DOMContentLoaded', function() {
    showLogin(); // Afficher le formulaire basé sur l'URL
    revealInitialErrors();
});

function revealInitialErrors(){
    const errorSelectors = [
        '.form-error-summary',
        '.error-box',
        '.error-text',
        '.alert-list .alert-danger',
        '.alert-list .alert-error',
        '.alert-list .alert-warning'
    ];
    const firstError = document.querySelector(errorSelectors.join(','));

    document.querySelectorAll('.form-group .error-text, p .error-text, .station-row .error-text').forEach(errorNode => {
        const group = errorNode.closest('.form-group, p, .station-row');
        if (!group) {
            return;
        }
        group.classList.add('field-has-error');
    });

    if (!firstError) {
        return;
    }

    requestAnimationFrame(() => {
        firstError.scrollIntoView({ block: 'center', behavior: 'auto' });

        const focusTarget = firstError.closest('.form-group, p, .station-row')?.querySelector('input, select, textarea');
        if (focusTarget && typeof focusTarget.focus === 'function') {
            focusTarget.focus({ preventScroll: true });
        }
    });
}

function applyDark(){
    document.body.setAttribute('data-dark', S.dark ? '1' : '0');
    const ic = document.getElementById('darkIcon');
    const lb = document.getElementById('darkLabel');
    if(ic) ic.className = S.dark ? 'fas fa-sun' : 'fas fa-moon';
    if(lb) lb.textContent = S.dark ? 'Light Mode' : 'Dark Mode';
}

function toggleDark(){ S.dark = !S.dark; localStorage.setItem('mc_dark', S.dark ? '1' : '0'); applyDark(); }

function showLogin(){
    const path = window.location.pathname;
    // Masquer toutes les étapes (seulement si elles existent)
    ['step1', 'stepAdmin', 'stepStudent', 'stepDriver', 'stepStudentChoice'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.classList.add('hidden');
    });
    // Afficher basé sur le chemin (seulement si l'élément existe)
    if (path === '/' && document.getElementById('step1')) {
        document.getElementById('step1').classList.remove('hidden');
    } else if (path === '/administrateur/' && document.getElementById('stepAdmin')) {
        document.getElementById('stepAdmin').classList.remove('hidden');
    } else if (path === '/etudiant/' && document.getElementById('stepStudentChoice')) {
        document.getElementById('stepStudentChoice').classList.remove('hidden');
    } else if (path === '/conducteur/' && document.getElementById('stepDriver')) {
        document.getElementById('stepDriver').classList.remove('hidden');
    }
}

function backToRoles(){
    if (window.location.pathname !== '/') {
        history.replaceState(null, '', '/');
        location.reload();
        return;
    }
    ['stepAdmin','stepStudent','stepDriver','stepStudentChoice'].forEach(id=>{
        const el = document.getElementById(id);
        if (el) el.classList.add('hidden');
    });
    const step1 = document.getElementById('step1');
    if (step1) step1.classList.remove('hidden');
    const adminPass = document.getElementById('adminPass');
    if (adminPass) adminPass.value = '';
    const studentId = document.getElementById('studentId');
    if (studentId) studentId.value = '';
    const driverId = document.getElementById('driverId');
    if (driverId) driverId.value = '';
    const sdCount = document.getElementById('sdCount');
    if (sdCount) sdCount.textContent = '0 / 8';
}


function showStudentLogin(){
    const choice = document.getElementById('studentChoice');
    if (choice) {
        choice.classList.add('hidden');
    } else {
        document.getElementById('stepStudentChoice').classList.add('hidden');
    }
    document.getElementById('stepStudent').classList.remove('hidden');
}

function backToStudentChoice(){
    document.getElementById('stepStudent').classList.add('hidden');
    const choice = document.getElementById('studentChoice');
    if (choice) {
        choice.classList.remove('hidden');
    } else {
        document.getElementById('stepStudentChoice').classList.remove('hidden');
    }
    document.getElementById('studentId').value = '';
    document.getElementById('sdCount').textContent = '0 / 8';
}

function loginAdmin(){
    if(document.getElementById('adminPass').value===ADMIN_PASS){ enterApp('admin','Admin'); }
    else showErr('adminErr','Wrong password');
}

function loginDriver(){
    const id = document.getElementById('driverId').value.trim().toUpperCase();
    if(!S.data.drivers.find(d=>d.id.toUpperCase()===id)) return showErr('driverErr','Driver ID not found');
    enterApp('driver', id);
}

function showErr(elId, msg){
    const el = document.getElementById(elId);
    el.textContent = msg; el.classList.remove('hidden');
    setTimeout(()=>el.classList.add('hidden'), 3000);
}

function enterApp(role, uid){
    S.role = role; S.uid = uid;
    if (role === 'student' && location.pathname !== '/etudiant/') {
        history.replaceState(null, '', '/etudiant/');
    }
    if (role === 'driver' && location.pathname !== '/conducteur/') {
        history.replaceState(null, '', '/conducteur/');
    }
    document.getElementById('loginScreen').classList.add('hidden');
    document.getElementById('appLayout').classList.remove('hidden');
    applyDark();
    buildSidebar();
    nav({admin:'dashboard', student:'home', driver:'driverHome'}[role]);
    const badge = document.getElementById('userBadge');
    badge.className = 'user-badge badge-'+role;
    badge.innerHTML = `<i class="fas ${role==='admin'?'fa-user-shield':role==='student'?'fa-user-graduate':'fa-id-card'}"></i> ${uid}`;
}

function confirmLogout(){ 
    const logoutModal = document.getElementById('logoutModal');
    if (logoutModal) logoutModal.classList.remove('hidden'); 
}
function closeLogout(){ 
    const logoutModal = document.getElementById('logoutModal');
    if (logoutModal) logoutModal.classList.add('hidden'); 
}
function executeLogout(){
    closeLogout();
    S.role=''; S.uid=''; S.view='';
    document.getElementById('appLayout').classList.add('hidden');
    const login = document.getElementById('loginScreen');
    login.style.opacity='0';
    login.classList.remove('hidden');
    login.style.transition='opacity .5s ease-in';
    setTimeout(()=>login.style.opacity='1', 30);
    backToRoles();
    document.getElementById('adminPass').value='';
    document.getElementById('studentId').value='';
    document.getElementById('driverId').value='';
    document.getElementById('sdCount').textContent='0 / 8';
}

const MENUS = {
    admin: [
        {id:'dashboard',icon:'fa-chart-pie',label:'Dashboard'},
        {id:'lines',icon:'fa-route',label:'Lines'},
        {id:'stations',icon:'fa-map-marker-alt',label:'Stations'},
        {id:'buses',icon:'fa-bus',label:'Buses'},
        {id:'drivers',icon:'fa-id-card',label:'Drivers'},
        {id:'reservations',icon:'fa-ticket-alt',label:'Reservations'},
        {id:'incidents',icon:'fa-exclamation-triangle',label:'Incidents'},
        {id:'ai',icon:'fa-robot',label:'AI Assistant'}
    ],
    student: [
        {id:'home',icon:'fa-home',label:'Home'},
        {id:'myreservations',icon:'fa-ticket-alt',label:'My Reservations'},
        {id:'stations',icon:'fa-map-marker-alt',label:'Stations'},
        {id:'incidents',icon:'fa-exclamation-triangle',label:'Report'},
        {id:'ai',icon:'fa-robot',label:'AI'}
    ],
    driver: [
        {id:'driverHome',icon:'fa-home',label:'My Dashboard'},
        {id:'driverSchedule',icon:'fa-clock',label:'My Schedule'},
        {id:'driverIncidents',icon:'fa-exclamation-triangle',label:'Report Incident'},
        {id:'driverMyIncidents',icon:'fa-list',label:'My Reports'}
    ]
};

function buildSidebar(){
    document.getElementById('sidebarNav').innerHTML = MENUS[S.role].map(m => `
        <button class="nav-btn${S.view===m.id?' active':''}" onclick="nav('${m.id}')">
            <i class="fas ${m.icon}"></i><span>${m.label}</span>
        </button>`).join('');
}

function nav(viewId){
    S.view = viewId; buildSidebar();
    const titles = {
        dashboard:'Dashboard', lines:'Lines', stations:'Stations', buses:'Buses', drivers:'Drivers', reservations:'Reservations', incidents:'Incidents', ai:'AI Assistant', home:'Home', myreservations:'My Reservations', driverHome:'My Dashboard', driverSchedule:'My Schedule', driverIncidents:'Report Incident', driverMyIncidents:'My Reports'
    };
    document.getElementById('pageTitle').textContent = titles[viewId] || viewId;
    const vc = document.getElementById('viewContainer');
    vc.innerHTML = '';
    const views = {
        dashboard:viewAdminDash, lines:viewLines, stations:viewStations, buses:viewBuses, drivers:viewDrivers, reservations:viewReservations, incidents:viewAdminIncidents, ai:viewAI,
        home:viewStudentHome, myreservations:viewMyReservations,
        driverHome:viewDriverHome, driverSchedule:viewDriverSchedule, driverIncidents:viewDriverReport, driverMyIncidents:viewDriverMyIncidents
    };
    if(views[viewId]) vc.innerHTML = views[viewId]();
    if(viewId==='home') setTimeout(updateBusOpts, 50);
}

function viewAdminDash(){
    const cap = S.data.buses.reduce((a,b)=>a+b.capacity,0);
    const res = S.data.buses.reduce((a,b)=>a+b.reserved,0);
    const occ = cap>0?((res/cap)*100).toFixed(0):0;
    return `
        <div class="stat-grid">
            <div class="stat"><div class="num">${S.data.lines.filter(l=>l.status==='active').length}</div><div class="lbl">Active Lines</div></div>
            <div class="stat"><div class="num">${S.data.buses.length}</div><div class="lbl">Buses</div></div>
            <div class="stat"><div class="num">${S.data.reservations.length}</div><div class="lbl">Reservations</div></div>
            <div class="stat"><div class="num" style="color:#f59e0b">${S.data.incidents.filter(i=>i.status==='pending').length}</div><div class="lbl">Pending Incidents</div></div>
            <div class="stat"><div class="num">${occ}%</div><div class="lbl">Occupancy</div></div>
            <div class="stat"><div class="num">${S.data.drivers.length}</div><div class="lbl">Drivers</div></div>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
            <div class="panel">
                <h3><i class="fas fa-bus" style="color:var(--brand)"></i> Bus Status</h3>
                ${S.data.buses.map(b=>{const pct=((b.reserved/b.capacity)*100).toFixed(0);const full=b.reserved>=b.capacity;return`<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 0;border-bottom:1px solid var(--border)"><div><div style="display:flex;align-items:center;gap:6px;font-size:13px;font-weight:600;color:var(--text)"><span class="dot ${full?'dot-red':'dot-green'}"></span>${b.name}${full?' <span class="tag tag-urgent" style="margin-left:4px">FULL</span>':''}</div><div style="font-size:11px;color:var(--muted)">${b.reserved}/${b.capacity} • ${b.time}</div></div><span class="tag tag-${pct>80?'urgent':pct>50?'medium':'low'}">${pct}%</span></div>`}).join('')}
            </div>
            <div class="panel">
                <h3><i class="fas fa-exclamation-triangle" style="color:#f59e0b"></i> Recent Incidents</h3>
                ${S.data.incidents.slice(-5).reverse().map(i=>`<div style="padding:8px 0;border-bottom:1px solid var(--border)"><div style="font-size:12px;font-weight:600;color:var(--text)">${i.aiCategory||'Unclassified'} — <span class="tag tag-${i.status==='resolved'?'resolved':'pending'}">${i.status}</span></div><div style="font-size:11px;color:var(--muted);margin-top:2px">${i.description.substring(0,60)}...</div></div>`).join('')||'<p style="font-size:13px;color:var(--muted)">No incidents</p>'}
            </div>
        </div>`;
}

function viewLines(){
    return `
        <div class="panel"><h3><i class="fas fa-plus-circle" style="color:var(--brand)"></i> Add Line</h3><div class="form-row"><div class="form-group"><label>Line Name</label><input id="nl_name" placeholder="e.g. Ligne 3 - ..."></div><div class="form-group"><label>Station</label><select id="nl_station">${S.data.stations.map(s=>`<option>${s}</option>`).join('')}</select></div></div><div class="form-row"><div class="form-group"><label>Departure Time</label><input type="time" id="nl_time" value="08:00"></div><div class="form-group" style="align-self:flex-end"><button class="btn-primary" onclick="addLine()"><i class="fas fa-plus"></i> Add Line</button></div></div></div>
        <div class="panel" style="padding:0;overflow:hidden"><table><thead><tr><th>Line</th><th>Station</th><th>Time</th><th>Status</th><th>Actions</th></tr></thead><tbody>${S.data.lines.map((l,i)=>`<tr><td style="font-weight:600">${l.name}</td><td>${l.station||'—'}</td><td><input type="time" value="${l.nextTime}" onchange="updateLineTime(${i},this.value)" style="width:100px;padding:4px 8px;font-size:12px"></td><td><span class="tag tag-${l.status==='active'?'active':'inactive'}">${l.status}</span></td><td style="display:flex;gap:6px"><button class="action-btn btn-edit" onclick="toggleLine(${i})">${l.status==='active'?'Disable':'Enable'}</button><button class="action-btn btn-del" onclick="deleteLine(${i})">Delete</button></td></tr>`).join('')}</tbody></table></div>`;
}

function viewStations(){
    return `
        <div class="panel"><h3><i class="fas fa-plus-circle" style="color:var(--brand)"></i> Add Station</h3><div style="display:flex;gap:10px"><input id="ns_name" placeholder="Station name" style="flex:1"><button class="btn-primary" onclick="addStation()"><i class="fas fa-plus"></i> Add</button></div></div>
        <div class="panel" style="padding:0;overflow:hidden"><table><thead><tr><th>#</th><th>Station</th><th>Lines</th><th>Action</th></tr></thead><tbody>${S.data.stations.map((s,i)=>{const lines=S.data.lines.filter(l=>l.station===s);return`<tr><td style="color:var(--muted)">${i+1}</td><td style="font-weight:600">${s}</td><td>${lines.map(l=>`<span class="tag tag-${l.status==='active'?'active':'inactive'}" style="margin-right:4px">${l.name.split(' ').slice(0,2).join(' ')}</span>`).join('')||'<span style="color:var(--muted);font-size:12px">None</span>'}</td><td><button class="action-btn btn-del" onclick="deleteStation(${i})">Delete</button></td></tr>`;}).join('')}</tbody></table></div>`;
}

function viewBuses(){
    return `
        <div class="panel"><h3><i class="fas fa-plus-circle" style="color:var(--brand)"></i> Add Bus</h3><div class="form-row"><div class="form-group"><label>Name</label><input id="nb_name" placeholder="Bus 03"></div><div class="form-group"><label>Capacity</label><input type="number" id="nb_cap" value="50" min="1"></div></div><div class="form-row"><div class="form-group"><label>Line</label><select id="nb_line"><option value="">-- Select --</option>${S.data.lines.map(l=>`<option value="${l.name}">${l.name}</option>`).join('')}</select></div><div class="form-group"><label>Time</label><input type="time" id="nb_time" value="08:00"></div></div><button class="btn-primary" onclick="addBus()"><i class="fas fa-plus"></i> Add Bus</button></div>
        <div class="panel" style="padding:0;overflow:hidden"><table><thead><tr><th>Bus</th><th>Line</th><th>Capacity</th><th>Reserved</th><th>Time</th><th>Actions</th></tr></thead><tbody>${S.data.buses.map((b,i)=>{const full=b.reserved>=b.capacity;return`<tr><td style="font-weight:600"><div style="display:flex;align-items:center;gap:6px"><span class="dot ${full?'dot-red':'dot-green'}"></span>${b.name}</div></td><td style="font-size:12px">${b.line}</td><td>${b.capacity}</td><td>${b.reserved}</td><td>${b.time}</td><td style="display:flex;gap:6px"><button class="action-btn btn-edit" onclick="editBus(${i})">Edit</button><button class="action-btn btn-del" onclick="deleteBus(${i})">Delete</button></td></tr>`;}).join('')}</tbody></table></div>`;
}

function viewDrivers(){
    return `
        <div class="panel"><h3><i class="fas fa-plus-circle" style="color:var(--brand)"></i> Add Driver</h3><div class="form-row"><div class="form-group"><label>Driver ID</label><input id="nd_id" placeholder="DRV-003"></div><div class="form-group"><label>Full Name</label><input id="nd_name" placeholder="Name"></div></div><div class="form-row"><div class="form-group"><label>Assigned Line</label><select id="nd_line"><option value="">-- Select --</option>${S.data.lines.map(l=>`<option value="${l.name}">${l.name}</option>`).join('')}</select></div><div class="form-group"><label>Shift Time</label><input type="time" id="nd_time" value="08:00"></div></div><div class="form-group" style="margin-bottom:10px"><label>Station</label><select id="nd_station"><option value="">-- Select --</option>${S.data.stations.map(s=>`<option value="${s}">${s}</option>`).join('')}</select></div><button class="btn-primary" onclick="addDriver()"><i class="fas fa-plus"></i> Add Driver</button></div>
        <div class="driver-grid">${S.data.drivers.map((d,i)=>{const line=S.data.lines.find(l=>l.name===d.line);const active=line&&line.status==='active';const inc=S.data.incidents.filter(x=>x.driverId===d.id&&x.status==='pending').length;const ls=d.line?(d.line.match(/Ligne\s*\d+/i)?.[0]||d.line.split('—')[0].trim()):'—';return`<div class="driver-card" onclick="editDriver(${i})">${inc>0?`<span style="position:absolute;top:6px;left:6px;width:16px;height:16px;background:#f59e0b;border-radius:50%;font-size:9px;font-weight:700;color:#fff;display:flex;align-items:center;justify-content:center">${inc}</span>`:''}<button onclick="event.stopPropagation();deleteDriver(${i})" style="position:absolute;top:6px;right:6px;width:18px;height:18px;background:#fee2e2;border:none;border-radius:50%;cursor:pointer;font-size:9px;color:#991b1b">✕</button><div class="driver-avatar"><i class="fas fa-user-tie"></i><span style="position:absolute;bottom:1px;right:1px;width:14px;height:14px;border-radius:50%;border:2px solid var(--card);background:${active?'#22c55e':'#94a3b8'}"></span></div><div class="driver-line-label">${ls}</div></div>`;}).join('')}</div>`;
}

function viewReservations(){
    const res = S.data.reservations;
    return `
        <div class="stat-grid" style="margin-bottom:16px"><div class="stat"><div class="num">${res.length}</div><div class="lbl">Total</div></div><div class="stat"><div class="num">${new Set(res.map(r=>r.studentId)).size}</div><div class="lbl">Students</div></div><div class="stat"><div class="num">${new Set(res.map(r=>r.bus)).size}</div><div class="lbl">Buses Used</div></div></div>
        <div class="panel" style="padding:0;overflow:hidden"><table><thead><tr><th>Student</th><th>Bus</th><th>Line</th><th>Station</th><th>Time</th><th>Actions</th></tr></thead><tbody>${res.length===0?`<tr><td colspan="6" style="text-align:center;color:var(--muted);padding:24px">No reservations</td></tr>`:res.map((r,i)=>`<tr><td><span class="tag" style="background:#dbeafe;color:#1e40af;font-family:monospace">${r.studentId}</span></td><td>${r.bus}</td><td style="font-size:11px">${r.line}</td><td style="font-size:11px">${r.station}</td><td>${r.time}</td><td style="display:flex;gap:6px"><button class="action-btn btn-edit" onclick="editReservation(${i})">Edit</button><button class="action-btn btn-del" onclick="deleteReservation(${i})">Delete</button></td></tr>`).join('')}</tbody></table></div>`;
}

function viewAdminIncidents(){
    const inc = S.data.incidents;
    return `
        <div class="stat-grid" style="margin-bottom:16px"><div class="stat"><div class="num" style="color:#f59e0b">${inc.filter(i=>i.status==='pending').length}</div><div class="lbl">Pending</div></div><div class="stat"><div class="num" style="color:#22c55e">${inc.filter(i=>i.status==='resolved').length}</div><div class="lbl">Resolved</div></div><div class="stat"><div class="num" style="color:#ef4444">${inc.filter(i=>i.aiSeverity==='Urgent').length}</div><div class="lbl">Urgent</div></div></div>
        ${inc.length===0?`<div class="panel"><p style="color:var(--muted);text-align:center;font-size:13px">No incidents</p></div>`:inc.slice().reverse().map((ic,ri)=>{const i=S.data.incidents.length-1-ri;const isDriver=ic.role==='driver';return`<div class="panel" style="border-left:4px solid ${ic.status==='resolved'?'#22c55e':'#f59e0b'}"><div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px"><div><div style="font-size:13px;font-weight:700;color:var(--text)">${ic.description}</div><div style="font-size:11px;color:var(--muted);margin-top:3px">${isDriver?`<span class="tag" style="background:#dcfce7;color:#166534;margin-right:6px"><i class="fas fa-id-card"></i> Driver: ${ic.uid}</span>`:`<span class="tag" style="background:#dbeafe;color:#1e40af;margin-right:6px"><i class="fas fa-user-graduate"></i> Student: ${ic.uid}</span>`}${ic.timestamp}</div></div><span class="tag tag-${ic.status==='resolved'?'resolved':'pending'}" style="white-space:nowrap">${ic.status}</span></div>${ic.aiCategory?`<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px"><span class="tag tag-${ic.aiSeverity==='Urgent'?'urgent':ic.aiSeverity==='Medium'?'medium':'low'}">${ic.aiSeverity}</span><span class="tag tag-inactive">${ic.aiCategory}</span></div>`:''}${ic.aiSuggestion?`<div style="font-size:12px;background:var(--bg);padding:8px 12px;border-radius:8px;color:var(--text);margin-bottom:8px"><strong>AI Suggestion:</strong> ${ic.aiSuggestion}</div>`:''}${ic.aiLineWarning?`<div style="font-size:12px;background:#fee2e2;padding:8px 12px;border-radius:8px;color:#991b1b;margin-bottom:8px"><strong>⚠ Warning:</strong> ${ic.aiLineWarning}</div>`:''}<div style="display:flex;gap:8px;flex-wrap:wrap">${ic.status!=='resolved'?`<button class="action-btn btn-green" onclick="resolveIncident(${i})">Mark Resolved</button>`:''}${ic.aiAffectedLine?`<button class="action-btn btn-del" onclick="disableLine('${ic.aiAffectedLine}')">Disable Line</button>`:''}<button class="action-btn btn-del" onclick="deleteIncident(${i})">Delete</button></div></div>`;}).join('')}
    `;
}

function viewStudentHome(){
    const myRes = S.data.reservations.filter(r=>r.studentId===S.uid);
    const activeLines = S.data.lines.filter(l=>l.status==='active');
    return `
        <div style="background:linear-gradient(135deg,var(--brand),#0369a1);color:#fff;border-radius:16px;padding:20px 24px;margin-bottom:16px"><div style="font-size:20px;font-weight:800">Welcome, ${S.uid}!</div><div style="font-size:13px;opacity:.8;margin-top:4px">${myRes.length} active reservation(s)</div></div>
        <div class="stat-grid" style="margin-bottom:16px"><div class="stat"><div class="num">${myRes.length}</div><div class="lbl">My Reservations</div></div><div class="stat"><div class="num">${activeLines.length}</div><div class="lbl">Active Lines</div></div><div class="stat"><div class="num">${S.data.stations.length}</div><div class="lbl">Stations</div></div></div>
        <div class="panel"><h3><i class="fas fa-ticket-alt" style="color:var(--brand)"></i> Book a Bus</h3><div class="form-group" style="margin-bottom:10px"><label>Line</label><select id="bk_line" onchange="updateBusOpts()">${activeLines.length===0?'<option>No active lines</option>':activeLines.map(l=>`<option value="${l.name}">${l.name} (${l.nextTime})</option>`).join('')}</select></div><div class="form-group" style="margin-bottom:10px"><label>Station</label><select id="bk_station">${S.data.stations.map(s=>`<option>${s}</option>`).join('')}</select></div><div class="form-group" style="margin-bottom:14px"><label>Bus</label><select id="bk_bus"></select></div><button class="btn-primary" style="width:100%;justify-content:center" onclick="reserve()"><i class="fas fa-check"></i> Reserve</button><div id="bk_msg" style="text-align:center;font-size:13px;margin-top:8px"></div></div>`;
}

function viewMyReservations(){
    const myRes = S.data.reservations.map((r,i)=>({...r,gi:i})).filter(r=>r.studentId===S.uid);
    return `
        <div class="panel"><h3><i class="fas fa-ticket-alt" style="color:var(--brand)"></i> My Reservations (${myRes.length})</h3>${myRes.length===0?'<p style="color:var(--muted);text-align:center;font-size:13px;padding:20px">No reservations yet</p>':myRes.map(r=>{const bus=S.data.buses.find(b=>b.name===r.bus);const full=bus&&bus.reserved>=bus.capacity;return`<div style="padding:12px;border-radius:10px;border:1px solid ${full?'#fbbf24':'var(--border)'};background:${full?'#fef9c3':'var(--bg)'};margin-bottom:8px;display:flex;justify-content:space-between;align-items:center"><div><div style="font-size:13px;font-weight:700;color:${full?'#854d0e':'var(--text)'}"><span class="dot ${full?'':'dot-green'}" style="${full?'background:#f59e0b':''};margin-right:6px"></span>${r.bus} — ${r.line}${full?' ⚠ Problem':''}</div><div style="font-size:11px;color:var(--muted);margin-top:3px">Station: ${r.station} • Departs: ${r.time}</div><div style="font-size:10px;color:var(--muted)">Booked: ${r.bookedAt}</div></div><button class="action-btn btn-del" onclick="cancelReservation(${r.gi})">Cancel</button></div>`;}).join('')}</div>`;
}

function getDriver(){ return S.data.drivers.find(d=>d.id.toUpperCase()===S.uid.toUpperCase()); }

function viewDriverHome(){
    const drv = getDriver();
    if(!drv) return '<div class="panel"><p style="color:var(--muted)">Driver not found</p></div>';
    const line = S.data.lines.find(l=>l.name===drv.line);
    const bus = S.data.buses.find(b=>b.line===drv.line);
    const myInc = S.data.incidents.filter(i=>i.driverId===drv.id);
    const myNotifs = S.data.notifications.filter(n=>n.driverId===drv.id && !n.read);
    return `
        <div style="background:linear-gradient(135deg,#15803d,#0369a1);color:#fff;border-radius:16px;padding:20px 24px;margin-bottom:16px"><div style="font-size:11px;opacity:.7;text-transform:uppercase;letter-spacing:.5px">Welcome back</div><div style="font-size:22px;font-weight:800;margin-top:2px">${drv.name}</div><div style="font-size:13px;opacity:.8;margin-top:4px">${drv.id}</div></div>
        ${myNotifs.length>0?`<div class="alert-box alert-change"><div style="font-weight:700;font-size:13px;margin-bottom:4px">⚠ Schedule Updated!</div>${myNotifs.map(n=>`<div style="font-size:12px;margin-top:4px">• ${n.message}</div>`).join('')}<button onclick="markNotifsRead('${drv.id}')" style="margin-top:8px;padding:4px 12px;border-radius:6px;border:none;background:#854d0e;color:#fff;font-size:11px;cursor:pointer">Mark as Read</button></div>`:''}
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px"><div class="info-box"><div class="label">Assigned Line</div><div class="value" style="font-size:13px">${drv.line||'—'}</div><div style="margin-top:6px"><span class="tag tag-${line&&line.status==='active'?'active':'inactive'}">${line?line.status:'inactive'}</span></div></div><div class="info-box"><div class="label">Station</div><div class="value">${drv.station||'—'}</div></div><div class="info-box"><div class="label">Shift Time</div><div class="value">${drv.time||'—'}</div></div><div class="info-box"><div class="label">Bus Occupancy</div><div class="value">${bus?`${bus.reserved}/${bus.capacity}`:'—'}</div>${bus&&bus.reserved>=bus.capacity?'<div style="margin-top:4px"><span class="tag tag-urgent">FULL</span></div>':''}</div></div>
        <div class="stat-grid"><div class="stat"><div class="num" style="color:#f59e0b">${myInc.filter(i=>i.status==='pending').length}</div><div class="lbl">My Pending Reports</div></div><div class="stat"><div class="num" style="color:#22c55e">${myInc.filter(i=>i.status==='resolved').length}</div><div class="lbl">Resolved</div></div></div>`;
}

function viewDriverSchedule(){
    const drv = getDriver();
    if(!drv) return '<div class="panel"><p style="color:var(--muted)">Driver not found</p></div>';
    const line = S.data.lines.find(l=>l.name===drv.line);
    const bus = S.data.buses.find(b=>b.line===drv.line);
    const reservations = S.data.reservations.filter(r=>r.bus===bus?.name);
    return `
        <div class="panel"><h3><i class="fas fa-route" style="color:var(--brand)"></i> My Line</h3><div class="info-box"><div class="label">Line Name</div><div class="value">${drv.line||'Not assigned'}</div></div><div class="info-box"><div class="label">Status</div><div class="value"><span class="tag tag-${line&&line.status==='active'?'active':'inactive'}">${line?line.status:'inactive'}</span></div></div><div class="info-box"><div class="label">Departure Time</div><div class="value">${line?line.nextTime:'—'}</div></div></div>
        <div class="panel"><h3><i class="fas fa-map-marker-alt" style="color:var(--brand)"></i> My Station</h3><div class="info-box"><div class="label">Assigned Station</div><div class="value">${drv.station||'—'}</div></div></div>
        <div class="panel"><h3><i class="fas fa-bus" style="color:var(--brand)"></i> My Bus</h3>${bus?`<div class="info-box"><div class="label">Bus</div><div class="value">${bus.name}</div></div><div class="info-box"><div class="label">Capacity</div><div class="value">${bus.capacity} seats</div></div><div class="info-box"><div class="label">Reserved</div><div class="value">${bus.reserved}/${bus.capacity}${bus.reserved>=bus.capacity?' <span class="tag tag-urgent" style="margin-left:8px">FULL</span>':''}</div></div><div style="margin-top:8px"><div style="font-size:11px;color:var(--muted);margin-bottom:4px">Occupancy</div><div style="background:var(--bg);border-radius:6px;height:8px;overflow:hidden"><div style="background:var(--brand);height:8px;width:${Math.min(100,(bus.reserved/bus.capacity)*100).toFixed(0)}%;border-radius:6px"></div></div></div><div style="margin-top:12px;font-size:12px;color:var(--muted)">${reservations.length} student(s) reserved on this bus</div>`:'<p style="font-size:13px;color:var(--muted)">No bus assigned to your line</p>'}</div>`;
}

function viewDriverReport(){
    return `
        <div class="panel"><h3><i class="fas fa-exclamation-triangle" style="color:var(--brand)"></i> Report an Incident</h3><div class="form-group" style="margin-bottom:12px"><label>Description</label><textarea id="drv_inc_desc" placeholder="Describe the issue clearly..." style="min-height:100px;resize:vertical"></textarea></div><button class="submit-btn" onclick="driverSubmitIncident()"><i class="fas fa-paper-plane"></i> Submit Report</button><div id="drv_inc_msg" style="text-align:center;font-size:13px;margin-top:8px"></div><div id="drv_ai_box" class="hidden" style="margin-top:12px;background:var(--bg);border:1px solid var(--border);border-radius:10px;padding:12px"><div style="font-size:11px;font-weight:700;color:#7c3aed;margin-bottom:6px"><i class="fas fa-robot"></i> AI Analysis</div><div id="drv_ai_content" style="font-size:12px;color:var(--muted)" class="msg-thinking">Analyzing...</div></div></div>`;
}

function viewDriverMyIncidents(){
    const drv = getDriver();
    const myInc = S.data.incidents.filter(i=>i.driverId===drv?.id).slice().reverse();
    return `
        <div class="panel"><h3><i class="fas fa-list" style="color:var(--brand)"></i> My Reports (${myInc.length})</h3>${myInc.length===0?'<p style="color:var(--muted);text-align:center;font-size:13px;padding:20px;">No reports submitted yet</p>':myInc.map(inc=>`<div style="padding:12px;border-radius:10px;border:1px solid var(--border);background:var(--bg);margin-bottom:8px;border-left:4px solid ${inc.status==='resolved'?'#22c55e':'#f59e0b'}"><div style="display:flex;justify-content:space-between;align-items:flex-start"><div style="font-size:13px;font-weight:600;color:var(--text);flex:1">${inc.description}</div><span class="tag tag-${inc.status==='resolved'?'resolved':'pending'}" style="margin-left:8px;white-space:nowrap">${inc.status}</span></div>${inc.aiCategory?`<div style="display:flex;gap:6px;margin-top:6px"><span class="tag tag-${inc.aiSeverity==='Urgent'?'urgent':inc.aiSeverity==='Medium'?'medium':'low'}">${inc.aiSeverity}</span><span class="tag tag-inactive">${inc.aiCategory}</span></div>`:''}${inc.aiSuggestion?`<div style="font-size:11px;color:var(--muted);margin-top:6px"><strong>Admin action:</strong> ${inc.aiSuggestion}</div>`:''}<div style="font-size:10px;color:var(--muted);margin-top:6px">${inc.timestamp}</div></div>`).join('')}</div>`;
}

function viewAI(){
    if(S.role==='driver') return `<div class="panel"><p style="color:var(--muted)">AI not available for drivers</p></div>`;
    const isAdmin = S.role==='admin';
    return `
        <div class="ai-grad"><div style="display:flex;align-items:center;gap:12px"><i class="fas fa-robot" style="font-size:28px"></i><div><div style="font-size:18px;font-weight:800">MyCous AI</div><div style="font-size:12px;opacity:.75">${isAdmin?'Network intelligence':'Personal assistant'}</div></div></div></div>
        ${isAdmin?`<div class="panel"><h3><i class="fas fa-magic" style="color:var(--brand)"></i> Network Analysis</h3><button class="btn-primary" onclick="runAnalysis()" style="margin-bottom:12px"><i class="fas fa-magic"></i> Analyze Network</button><div id="analysisResult"><p style="font-size:13px;color:var(--muted)">Click to run AI analysis</p></div></div>`:''}
        <div class="panel"><h3><i class="fas fa-comments" style="color:var(--brand)"></i> Chat</h3><div class="chat-box" id="chatBox"><div class="msg-ai"><i class="fas fa-robot" style="margin-right:4px;opacity:.7"></i>Hello! How can I help?</div></div><div class="chat-input-row"><input id="chatInput" placeholder="Ask me..." onkeydown="if(event.key==='Enter')sendChat()"><button class="chat-send" onclick="sendChat()"><i class="fas fa-paper-plane"></i></button></div></div>`;
}

function addLine(){
    const name=document.getElementById('nl_name').value.trim();
    const station=document.getElementById('nl_station').value;
    const time=document.getElementById('nl_time').value||'08:00';
    if(!name){alert('Enter line name');return;}
    S.data.lines.push({name,status:'inactive',nextTime:time,station});
    save('lines');
    nav('lines');
}

function toggleLine(i){
    const l=S.data.lines[i];
    l.status=l.status==='active'?'inactive':'active';
    save('lines');
    S.data.drivers.filter(d=>d.line===l.name).forEach(d=>{
        S.data.notifications.push({driverId:d.id,message:`Your line "${l.name}" has been ${l.status}.`,read:false,timestamp:new Date().toLocaleString()});
    });
    save('notifications');
    nav('lines');
}

function updateLineTime(i,time){
    const old=S.data.lines[i].nextTime;
    S.data.lines[i].nextTime=time;
    save('lines');
    if(old!==time){
        S.data.drivers.filter(d=>d.line===S.data.lines[i].name).forEach(d=>{
            S.data.notifications.push({driverId:d.id,message:`Departure time for "${S.data.lines[i].name}" changed from ${old} to ${time}.`,read:false,timestamp:new Date().toLocaleString()});
        });
        save('notifications');
    }
}

function deleteLine(i){ if(confirm('Delete line?')){ S.data.lines.splice(i,1); save('lines'); nav('lines'); } }

function addStation(){ const v=document.getElementById('ns_name').value.trim(); if(!v) return; S.data.stations.push(v); save('stations'); nav('stations'); }
function deleteStation(i){ if(confirm('Delete station?')){ S.data.stations.splice(i,1); save('stations'); nav('stations'); } }
function addBus(){ const name=document.getElementById('nb_name').value.trim(); const cap=parseInt(document.getElementById('nb_cap').value)||50; const line=document.getElementById('nb_line').value; const time=document.getElementById('nb_time').value||'08:00'; if(!name||!line){alert('Fill all fields');return;} S.data.buses.push({name,capacity:cap,reserved:0,line,time}); save('buses'); nav('buses'); }
function editBus(i){ const b=S.data.buses[i]; showModal(`<h3><i class="fas fa-bus" style="color:var(--brand)"></i> Edit Bus</h3><div class="form-group" style="margin-bottom:10px"><label>Name</label><input id="eb_name" value="${b.name}"></div><div class="form-group" style="margin-bottom:10px"><label>Capacity</label><input type="number" id="eb_cap" value="${b.capacity}" min="1"></div><div class="form-group" style="margin-bottom:10px"><label>Line</label><select id="eb_line">${S.data.lines.map(l=>`<option value="${l.name}" ${l.name===b.line?'selected':''}>${l.name}</option>`).join('')}</select></div><div class="form-group" style="margin-bottom:10px"><label>Time</label><input type="time" id="eb_time" value="${b.time}"></div><div class="modal-footer"><button class="btn-cancel" onclick="closeModal()">Cancel</button><button class="btn-save" onclick="saveBus(${i})">Save</button></div>`); }
function saveBus(i){ const old=S.data.buses[i]; const newLine=document.getElementById('eb_line').value; S.data.buses[i]={...old,name:document.getElementById('eb_name').value.trim(),capacity:parseInt(document.getElementById('eb_cap').value)||old.capacity,line:newLine,time:document.getElementById('eb_time').value||old.time}; save('buses'); closeModal(); nav('buses'); }
function deleteBus(i){ if(confirm('Delete bus?')){ S.data.buses.splice(i,1); save('buses'); nav('buses'); } }
function addDriver(){ const id=document.getElementById('nd_id').value.trim().toUpperCase(); const name=document.getElementById('nd_name').value.trim(); const line=document.getElementById('nd_line').value; const time=document.getElementById('nd_time').value||'08:00'; const station=document.getElementById('nd_station').value; if(!id||!name){alert('Fill ID and name');return;} if(S.data.drivers.find(d=>d.id.toUpperCase()===id)){alert('Driver ID already exists');return;} S.data.drivers.push({id,name,line,time,station}); save('drivers'); nav('drivers'); }
function editDriver(i){ const d=S.data.drivers[i]; showModal(`<h3><i class="fas fa-id-card" style="color:var(--brand)"></i> Edit Driver</h3><div class="form-group" style="margin-bottom:10px"><label>ID</label><input id="ed_id" value="${d.id}"></div><div class="form-group" style="margin-bottom:10px"><label>Name</label><input id="ed_name" value="${d.name}"></div><div class="form-group" style="margin-bottom:10px"><label>Line</label><select id="ed_line"><option value="">No line</option>${S.data.lines.map(l=>`<option value="${l.name}" ${l.name===d.line?'selected':''}>${l.name}</option>`).join('')}</select></div><div class="form-group" style="margin-bottom:10px"><label>Station</label><select id="ed_station"><option value="">No station</option>${S.data.stations.map(s=>`<option value="${s}" ${s===d.station?'selected':''}>${s}</option>`).join('')}</select></div><div class="form-group" style="margin-bottom:10px"><label>Shift Time</label><input type="time" id="ed_time" value="${d.time||'08:00'}"></div><div class="modal-footer"><button class="btn-cancel" onclick="closeModal()">Cancel</button><button class="btn-save" onclick="saveDriver(${i})">Save</button></div>`); }
function saveDriver(i){ const old=S.data.drivers[i]; const newLine=document.getElementById('ed_line').value; const newStation=document.getElementById('ed_station').value; const newTime=document.getElementById('ed_time').value; const changed=[]; if(old.line!==newLine) changed.push(`Line changed to "${newLine||'None'}"`); if(old.station!==newStation) changed.push(`Station changed to "${newStation||'None'}"`); if(old.time!==newTime) changed.push(`Shift time changed to ${newTime}`); S.data.drivers[i]={...old,id:document.getElementById('ed_id').value.trim(),name:document.getElementById('ed_name').value.trim(),line:newLine,station:newStation,time:newTime}; save('drivers'); if(changed.length>0){ S.data.notifications.push({driverId:S.data.drivers[i].id,message:changed.join('. ')+'.',read:false,timestamp:new Date().toLocaleString()}); save('notifications'); } closeModal(); nav('drivers'); }
function deleteDriver(i){ if(confirm('Remove driver?')){ S.data.drivers.splice(i,1); save('drivers'); nav('drivers'); } }
function deleteReservation(i){ const r=S.data.reservations[i]; const b=S.data.buses.find(x=>x.name===r.bus); if(b&&b.reserved>0) b.reserved--; S.data.reservations.splice(i,1); save('reservations'); save('buses'); }
function editReservation(i){ const r=S.data.reservations[i]; showModal(`<h3><i class="fas fa-edit" style="color:var(--brand)"></i> Edit Reservation</h3><div class="form-group" style="margin-bottom:10px"><label>Student ID</label><input id="er_sid" value="${r.studentId}" maxlength="8"></div><div class="form-group" style="margin-bottom:10px"><label>Bus</label><select id="er_bus">${S.data.buses.map(b=>`<option value="${b.name}" ${b.name===r.bus?'selected':''}>${b.name}</option>`).join('')}</select></div><div class="form-group" style="margin-bottom:10px"><label>Line</label><select id="er_line">${S.data.lines.map(l=>`<option value="${l.name}" ${l.name===r.line?'selected':''}>${l.name}</option>`).join('')}</select></div><div class="form-group" style="margin-bottom:10px"><label>Station</label><select id="er_station">${S.data.stations.map(s=>`<option value="${s}" ${s===r.station?'selected':''}>${s}</option>`).join('')}</select></div><div class="form-group" style="margin-bottom:10px"><label>Time</label><input type="time" id="er_time" value="${r.time}"></div><div class="modal-footer"><button class="btn-cancel" onclick="closeModal()">Cancel</button><button class="btn-save" onclick="saveReservation(${i})">Save</button></div>`); }
function saveReservation(i){ const sid=document.getElementById('er_sid').value.trim(); if(sid.length!==8||isNaN(sid)){alert('Student ID must be 8 digits');return;} S.data.reservations[i]={...S.data.reservations[i],studentId:sid,bus:document.getElementById('er_bus').value,line:document.getElementById('er_line').value,station:document.getElementById('er_station').value,time:document.getElementById('er_time').value}; save('reservations'); closeModal(); nav('reservations'); }
function resolveIncident(i){ S.data.incidents[i].status='resolved'; save('incidents'); nav('incidents'); }
function deleteIncident(i){ S.data.incidents.splice(i,1); save('incidents'); nav('incidents'); }
function disableLine(lineName){ const l=S.data.lines.find(x=>x.name===lineName); if(l){ l.status='inactive'; save('lines'); S.data.drivers.filter(d=>d.line===lineName).forEach(d=>{ S.data.notifications.push({driverId:d.id,message:`Your line "${lineName}" has been disabled due to an incident.`,read:false,timestamp:new Date().toLocaleString()}); }); save('notifications'); } nav('incidents'); }
function markNotifsRead(driverId){ S.data.notifications.filter(n=>n.driverId===driverId).forEach(n=>n.read=true); save('notifications'); nav('driverHome'); }
function updateBusOpts(){ const line=document.getElementById('bk_line')?.value; const sel=document.getElementById('bk_bus'); if(!sel) return; const buses=S.data.buses.filter(b=>b.line===line); sel.innerHTML=buses.length?buses.map(b=>`<option value="${b.name}">${b.name} (${b.capacity-b.reserved} free)</option>`).join(''):'<option>No buses on this line</option>'; }

function reserve(){ const line=document.getElementById('bk_line')?.value; const station=document.getElementById('bk_station')?.value; const busName=document.getElementById('bk_bus')?.value; const msg=document.getElementById('bk_msg'); if(!line||!busName){ msg.innerHTML='<span style="color:#ef4444">Select all fields</span>'; return; } const bus=S.data.buses.find(b=>b.name===busName); if(bus.reserved>=bus.capacity){ msg.innerHTML='<span style="color:#ef4444">Bus is full!</span>'; return; } bus.reserved++; S.data.reservations.push({studentId:S.uid,line,station,bus:busName,time:bus.time,bookedAt:new Date().toLocaleString()}); save('buses'); save('reservations'); msg.innerHTML='<span style="color:#22c55e;font-weight:700">✔ Reserved!</span>'; setTimeout(()=>nav('home'),900); }
function cancelReservation(gi){ const r=S.data.reservations[gi]; const b=S.data.buses.find(x=>x.name===r.bus); if(b&&b.reserved>0) b.reserved--; S.data.reservations.splice(gi,1); save('reservations'); save('buses'); nav('myreservations'); }
async function driverSubmitIncident(){ const desc=document.getElementById('drv_inc_desc')?.value.trim(); const msg=document.getElementById('drv_inc_msg'); const drv=getDriver(); if(!desc){ msg.innerHTML='<span style="color:#ef4444">Please describe the issue</span>'; return; } const incident={uid:S.uid,driverId:drv?.id,role:'driver',description:desc,timestamp:new Date().toLocaleString(),status:'pending',aiCategory:null,aiSeverity:null,aiSuggestion:null,aiLineWarning:null,aiAffectedLine:null}; S.data.incidents.push(incident); save('incidents'); msg.innerHTML='<span style="color:#22c55e">✔ Submitted!</span>'; document.getElementById('drv_ai_box').classList.remove('hidden'); await analyzeIncident(S.data.incidents.length-1,'drv_ai_content'); setTimeout(()=>nav('driverMyIncidents'),2000); }

async function analyzeIncident(idx, contentElId){ const inc=S.data.incidents[idx]; const lineNames=S.data.lines.map(l=>l.name).join(', '); try{ const res=await callClaude(`You are AI for MyCous, an Algerian university transport system.\nReported by ${inc.role}: "${inc.description}"\nAvailable lines: ${lineNames}\nRespond ONLY valid JSON, no markdown:\n{"category":"Delay|Breakdown|Overload|Behavior|Other","severity":"Urgent|Medium|Low","suggestion":"max 20 words","affectedLine":"exact line name or null","lineWarning":"warning or null"}`); const ai=JSON.parse(res.replace(/```json|```/g,'').trim()); S.data.incidents[idx].aiCategory=ai.category; S.data.incidents[idx].aiSeverity=ai.severity; S.data.incidents[idx].aiSuggestion=ai.suggestion; S.data.incidents[idx].aiLineWarning=ai.lineWarning; S.data.incidents[idx].aiAffectedLine=ai.affectedLine; save('incidents'); const el=document.getElementById(contentElId); if(el){ el.classList.remove('msg-thinking'); el.innerHTML=`<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:6px"><span class="tag tag-${ai.severity==='Urgent'?'urgent':ai.severity==='Medium'?'medium':'low'}">${ai.severity}</span><span class="tag tag-inactive">${ai.category}</span></div><div style="font-size:12px">${ai.suggestion}</div>${ai.lineWarning?`<div style="color:#991b1b;font-size:12px;margin-top:4px">⚠ ${ai.lineWarning}</div>`:''}`; } }catch(e){ const el=document.getElementById(contentElId); if(el) el.innerHTML=`<span style="color:#ef4444;font-size:12px">AI Error: ${e.message}</span>`; } }

async function sendChat(){ const input=document.getElementById('chatInput'); const q=input.value.trim(); const box=document.getElementById('chatBox'); if(!q) return; input.value=''; box.innerHTML+=`<div class="msg-user">${q}</div><div class="msg-ai msg-thinking" id="thinking">Thinking...</div>`; box.scrollTop=9999; const ctx={lines:S.data.lines,buses:S.data.buses,incidents:S.data.incidents,reservations:S.data.reservations.length,drivers:S.data.drivers.length}; try{ const r=await callClaude(`You are MyCous AI for ${S.role} "${S.uid}". Data: ${JSON.stringify(ctx)}. Question: "${q}". Answer in English, friendly, concise, max 80 words, use emojis.`); document.getElementById('thinking').remove(); box.innerHTML+=`<div class="msg-ai"><i class="fas fa-robot" style="margin-right:4px;opacity:.7"></i>${r}</div>`; box.scrollTop=9999; }catch(e){ document.getElementById('thinking').remove(); box.innerHTML+=`<div class="msg-ai" style="background:#fee2e2;color:#991b1b">Error: ${e.message}</div>`; } }

async function runAnalysis(){ const el=document.getElementById('analysisResult'); el.innerHTML='<p class="msg-thinking" style="font-size:13px;color:var(--muted)">Analyzing network...</p>'; const ctx={lines:S.data.lines,buses:S.data.buses,incidents:S.data.incidents,reservations:S.data.reservations.length}; try{ const r=await callClaude(`You are MyCous AI admin. Analyze: ${JSON.stringify(ctx)}. Give recommendations on lines, buses, incidents. English, structured, max 150 words.`); el.innerHTML=`<div style="background:var(--bg);border:1px solid var(--border);border-radius:10px;padding:14px;font-size:13px;color:var(--text);white-space:pre-wrap;line-height:1.6">${r}</div>`; }catch(e){ el.innerHTML=`<span style="color:#ef4444;font-size:13px">Error: ${e.message}</span>`; } }

async function callClaude(prompt){ const res=await fetch('https://api.anthropic.com/v1/messages',{method:'POST',headers:{'Content-Type':'application/json','x-api-key':'YOUR_API_KEY_HERE','anthropic-version':'2023-06-01','anthropic-dangerous-direct-browser-access':'true'},body:JSON.stringify({model:'claude-sonnet-4-20250514',max_tokens:800,messages:[{role:'user',content:prompt}]})}); const data=await res.json(); if(data.error) throw new Error(data.error.message); return data.content[0].text; }

function showModal(html){ document.getElementById('modalBox').innerHTML = html; document.getElementById('modalBg').classList.remove('hidden'); }
function closeModal(){ document.getElementById('modalBg').classList.add('hidden'); }

document.addEventListener('DOMContentLoaded', ()=>{
    applyDark();
    // Only attach modal listeners if elements exist
    const modalBg = document.getElementById('modalBg');
    if (modalBg) {
        modalBg.addEventListener('click', e => { if(e.target===modalBg) closeModal(); });
    }
    const logoutModal = document.getElementById('logoutModal');
    if (logoutModal) {
        logoutModal.addEventListener('click', e => { if(e.target===logoutModal) closeLogout(); });
    }
});

// Unified page scripts bundle.
(function () {
    var body = document.body;

    function hasPageClass(name) {
        return !!(body && body.classList.contains(name));
    }

    function isAdminShellPage() {
        return hasPageClass('page-driver-liste') ||
            hasPageClass('page-driver-home') ||
            hasPageClass('page-etudiants-par-ligne') ||
            hasPageClass('page-etudiants-sans-abonnement') ||
            hasPageClass('page-liste-bus-affectations') ||
            hasPageClass('page-liste-lignes') ||
            hasPageClass('page-bulk-assign-buses') ||
            hasPageClass('page-historique-modifications') ||
            hasPageClass('page-lignes-chargees') ||
            hasPageClass('page-remplissage-bus') ||
            hasPageClass('page-bus-trajets');
    }

    var legacy = {
        toggleDark: window.toggleDark,
        logout: window.logout,
        showPanel: window.showPanel,
        openFormPopup: window.openFormPopup,
        closeFormPopup: window.closeFormPopup,
        openAddLignePopup: window.openAddLignePopup,
        closeAddLignePopup: window.closeAddLignePopup,
        clearFilters: window.clearFilters,
        updateFiltersColors: window.updateFiltersColors,
        openDeleteModal: window.openDeleteModal,
        closeDeleteModal: window.closeDeleteModal,
        reserveTrajet: window.reserveTrajet,
        cancelReservation: window.cancelReservation,
        subscribeToLine: window.subscribeToLine,
        unsubscribe: window.unsubscribe
    };

    var AdminShell = (function () {
        var isClosingFormPopup = false;

        function normalizePath(path) {
            if (!path) {
                return '/';
            }
            return path.endsWith('/') ? path : path + '/';
        }

        function getConfig() {
            return body ? body.dataset : {};
        }

        function buildPopupUrl(url) {
            try {
                var absoluteUrl = new URL(url, window.location.origin);
                absoluteUrl.searchParams.set('popup', '1');
                absoluteUrl.searchParams.set('return_to', window.location.href);
                absoluteUrl.searchParams.set('_t', new Date().getTime().toString());
                return absoluteUrl.toString();
            } catch (error) {
                return url;
            }
        }

        function resolveToggleButton(button) {
            if (button) {
                return button;
            }
            return document.querySelector('.sidebar-bottom button');
        }

        function toggleDark(button) {
            if (!body) {
                return;
            }

            var next = body.getAttribute('data-dark') === '1' ? '0' : '1';
            var targetButton = resolveToggleButton(button);
            body.setAttribute('data-dark', next);

            if (targetButton) {
                targetButton.innerHTML = next === '1'
                    ? '<i class="fas fa-sun"></i> Mode Clair'
                    : '<i class="fas fa-moon"></i> Mode Sombre';
            }
        }

        function logout() {
            var config = getConfig();
            var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
            var confirmMessage = config.logoutConfirm;

            if (confirmMessage && !window.confirm(confirmMessage)) {
                return;
            }

            if (!config.logoutUrl) {
                return;
            }

            fetch(config.logoutUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken ? csrfToken.value : '',
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                body: csrfToken ? 'csrfmiddlewaretoken=' + encodeURIComponent(csrfToken.value) : ''
            }).then(function () {
                if (config.loginUrl) {
                    window.location.href = config.loginUrl;
                }
            }).catch(function () {
                if (config.loginUrl) {
                    window.location.href = config.loginUrl;
                }
            });
        }

        function ensureFormModal() {
            var modal = document.getElementById('formModal');
            if (modal) {
                return modal;
            }

            modal = document.createElement('div');
            modal.id = 'formModal';
            modal.className = 'hidden admin-form-modal';
            modal.innerHTML = [
                '<div class="admin-form-modal-card" role="dialog" aria-modal="true" aria-labelledby="formModalTitle">',
                '  <div class="admin-form-modal-head">',
                '    <h3 id="formModalTitle"><i id="formModalIcon" class="fas fa-plus"></i> <span id="formModalTitleText">Formulaire</span></h3>',
                '    <button type="button" class="admin-form-modal-close" aria-label="Fermer">&times;</button>',
                '  </div>',
                '  <iframe id="formModalFrame" class="admin-form-modal-frame" src="about:blank" title="Formulaire"></iframe>',
                '</div>'
            ].join('');

            modal.addEventListener('click', function (event) {
                if (event.target === modal) {
                    closeFormPopup();
                }
            });

            modal.querySelector('.admin-form-modal-close').addEventListener('click', closeFormPopup);

            var frame = modal.querySelector('#formModalFrame');
            frame.addEventListener('load', function () {
                if (isClosingFormPopup) {
                    return;
                }

                var returnUrl = modal.dataset.returnUrl || '';
                if (!returnUrl) {
                    return;
                }

                try {
                    var targetPath = normalizePath(new URL(returnUrl, window.location.origin).pathname);
                    var currentPath = normalizePath(frame.contentWindow.location.pathname);

                    if (targetPath === currentPath) {
                        closeFormPopup();
                        if (window.location.href === returnUrl) {
                            window.location.reload();
                        } else {
                            window.location.href = returnUrl;
                        }
                    }
                } catch (error) {
                    // Ignore URL parsing errors and keep modal open.
                }
            });

            document.body.appendChild(modal);
            return modal;
        }

        function openFormPopup(url, title, iconClass) {
            var modal = ensureFormModal();
            var frame = document.getElementById('formModalFrame');
            var titleText = document.getElementById('formModalTitleText');
            var icon = document.getElementById('formModalIcon');

            modal.dataset.returnUrl = window.location.href;
            frame.src = buildPopupUrl(url);
            titleText.textContent = title;
            icon.className = iconClass;
            modal.classList.remove('hidden');
            document.body.style.overflow = 'hidden';
        }

        function closeFormPopup() {
            var modal = document.getElementById('formModal');
            var frame = document.getElementById('formModalFrame');

            if (!modal || !frame) {
                return;
            }

            isClosingFormPopup = true;
            frame.src = 'about:blank';
            modal.classList.add('hidden');
            document.body.style.overflow = '';
            setTimeout(function () {
                isClosingFormPopup = false;
            }, 0);
        }

        function clearFilters() {
            var form = document.querySelector('form[method="get"]');
            if (!form) {
                return;
            }

            form.querySelectorAll('select').forEach(function (select) {
                select.selectedIndex = 0;
            });

            form.querySelectorAll('input').forEach(function (input) {
                if (input.type !== 'hidden') {
                    input.value = '';
                }
            });
        }

        return {
            toggleDark: toggleDark,
            logout: logout,
            openFormPopup: openFormPopup,
            closeFormPopup: closeFormPopup,
            clearFilters: clearFilters
        };
    })();

    var AdminDashboard = (function () {
        var popupStateKey = 'mycous.popupState:' + window.location.pathname;

        function getConfig() {
            return body ? body.dataset : {};
        }

        function savePopupState(state) {
            try {
                sessionStorage.setItem(popupStateKey, JSON.stringify(state));
            } catch (error) {
                // Ignore storage issues and keep the popup functional.
            }
        }

        function loadPopupState() {
            try {
                var rawState = sessionStorage.getItem(popupStateKey);
                return rawState ? JSON.parse(rawState) : null;
            } catch (error) {
                return null;
            }
        }

        function clearPopupState() {
            try {
                sessionStorage.removeItem(popupStateKey);
            } catch (error) {
                // Ignore storage issues.
            }
        }

        function openFormPopup(url, title, iconClass) {
            var modal = document.getElementById('formModal');
            var frame = document.getElementById('formModalFrame');
            var titleText = document.getElementById('formModalTitleText');
            var icon = document.getElementById('formModalIcon');

            if (!modal || !frame || !titleText || !icon) {
                return;
            }

            try {
                var absoluteUrl = new URL(url, window.location.origin);
                absoluteUrl.searchParams.set('popup', '1');
                absoluteUrl.searchParams.set('return_to', window.location.href);
                absoluteUrl.searchParams.set('_t', new Date().getTime().toString());
                frame.src = absoluteUrl.toString();
                savePopupState({
                    kind: 'form',
                    title: title || 'Formulaire',
                    iconClass: iconClass || 'fas fa-file-alt',
                    url: frame.src,
                    returnUrl: window.location.href
                });
            } catch (error) {
                frame.src = url;
                savePopupState({
                    kind: 'form',
                    title: title || 'Formulaire',
                    iconClass: iconClass || 'fas fa-file-alt',
                    url: url,
                    returnUrl: window.location.href
                });
            }
            modal.dataset.returnUrl = window.location.href;
            titleText.textContent = title;
            icon.className = iconClass;
            modal.classList.remove('hidden');
            document.body.style.overflow = 'hidden';
        }

        function closeFormPopup() {
            var modal = document.getElementById('formModal');
            var frame = document.getElementById('formModalFrame');

            if (!modal || !frame) {
                return;
            }

            modal.classList.add('hidden');
            frame.src = 'about:blank';
            clearPopupState();
            document.body.style.overflow = '';
        }

        function openAddLignePopup() {
            var config = getConfig();
            if (config.addLigneUrl) {
                openFormPopup(config.addLigneUrl, 'Ajouter une ligne', 'fas fa-route');
            }
        }

        function restorePopupState() {
            var savedState = loadPopupState();
            if (!savedState || !savedState.url) {
                return;
            }

            openFormPopup(savedState.url, savedState.title, savedState.iconClass);
        }

        function showPanel(panelName, button) {
            var config = getConfig();

            if (panelName === 'lignes') {
                window.location.href = config.lignesUrl;
                return;
            }

            if (panelName === 'bus') {
                window.location.href = config.busUrl;
                return;
            }

            if (panelName === 'rapports') {
                window.location.href = config.rapportsUrl;
                return;
            }

            document.querySelectorAll('main > div').forEach(function (panel) {
                panel.classList.add('hidden');
            });

            var target = document.getElementById(panelName + '-panel');
            if (target) {
                target.classList.remove('hidden');
            }

            document.querySelectorAll('.nav-btn').forEach(function (navButton) {
                navButton.classList.remove('active');
            });

            if (button) {
                button.classList.add('active');
            }
        }

        function toggleDark(button) {
            if (!body) {
                return;
            }

            var current = body.getAttribute('data-dark');
            var next = current === '0' ? '1' : '0';
            body.setAttribute('data-dark', next);

            if (button) {
                button.innerHTML = next === '1'
                    ? '<i class="fas fa-sun"></i> Mode Clair'
                    : '<i class="fas fa-moon"></i> Mode Sombre';
            }
        }

        function logout() {
            var config = getConfig();
            var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');

            fetch(config.logoutUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'X-CSRFToken': csrfToken ? csrfToken.value : ''
                },
                body: csrfToken ? 'csrfmiddlewaretoken=' + encodeURIComponent(csrfToken.value) : ''
            }).then(function (response) {
                if (response.ok) {
                    window.location.href = config.loginUrl;
                } else {
                    window.location.href = config.loginUrl;
                }
            }).catch(function () {
                window.location.href = config.loginUrl;
            });
        }

        return {
            openFormPopup: openFormPopup,
            closeFormPopup: closeFormPopup,
            openAddLignePopup: openAddLignePopup,
            restorePopupState: restorePopupState,
            showPanel: showPanel,
            toggleDark: toggleDark,
            logout: logout
        };
    })();

    var StudentHome = (function () {
        var subscriptions = [];
        var ratingModal = null;
        var ratingForm = null;
        var ratingSubmitBtn = null;

        function normalizeText(value) {
            return String(value || '').toLowerCase().trim();
        }

        function applyHistoryFilters() {
            var tbody = document.getElementById('full-history-tbody');
            if (!tbody) {
                return;
            }

            var rows = Array.from(tbody.querySelectorAll('tr[data-history-row="1"]'));
            if (!rows.length) {
                return;
            }

            var searchValue = normalizeText(document.getElementById('history-search') ? document.getElementById('history-search').value : '');
            var fromValue = document.getElementById('history-date-from') ? document.getElementById('history-date-from').value : '';
            var toValue = document.getElementById('history-date-to') ? document.getElementById('history-date-to').value : '';
            var lineValue = normalizeText(document.getElementById('history-line') ? document.getElementById('history-line').value : '');
            var sensValue = normalizeText(document.getElementById('history-sens') ? document.getElementById('history-sens').value : '');

            var visibleCount = 0;

            rows.forEach(function (row) {
                var rowDate = row.dataset.date || '';
                var rowLine = normalizeText(row.dataset.line);
                var rowSens = normalizeText(row.dataset.sens);
                var rowBus = normalizeText(row.dataset.bus);
                var rowStatus = normalizeText(row.dataset.status);
                var rowText = normalizeText(row.textContent);

                var matchesSearch = !searchValue || rowText.indexOf(searchValue) !== -1 || rowLine.indexOf(searchValue) !== -1 || rowBus.indexOf(searchValue) !== -1 || rowStatus.indexOf(searchValue) !== -1;
                var matchesFrom = !fromValue || rowDate >= fromValue;
                var matchesTo = !toValue || rowDate <= toValue;
                var matchesLine = !lineValue || rowLine === lineValue;
                var matchesSens = !sensValue || rowSens.indexOf(sensValue) !== -1;

                var isVisible = matchesSearch && matchesFrom && matchesTo && matchesLine && matchesSens;
                row.style.display = isVisible ? '' : 'none';
                if (isVisible) {
                    visibleCount += 1;
                }
            });

            var emptyFilterRow = document.getElementById('history-empty-filter-row');
            if (emptyFilterRow) {
                emptyFilterRow.classList.toggle('hidden', visibleCount > 0);
            }
        }

        function initHistoryFilters() {
            var filtersWrap = document.getElementById('historyFilters');
            if (!filtersWrap) {
                return;
            }

            filtersWrap.querySelectorAll('input, select').forEach(function (control) {
                control.addEventListener('input', applyHistoryFilters);
                control.addEventListener('change', applyHistoryFilters);
            });
        }

        function setPanelVisibility(panelId, isVisible) {
            var panel = document.getElementById(panelId);
            if (!panel) {
                return;
            }
            panel.style.display = isVisible ? 'block' : 'none';
        }

        function getConfig() {
            return body ? body.dataset : {};
        }

        function loadInitialSubscriptions() {
            var encodedData = getConfig().subscriptions;
            if (!encodedData) {
                return [];
            }

            try {
                return JSON.parse(encodedData);
            } catch (error) {
                console.error('Invalid subscriptions JSON:', error);
                return [];
            }
        }

        function showPanel(panel) {
            var panelMap = {
                dashboard: 'dashboard-panel',
                trips: 'trips-panel',
                history: 'history-panel',
                subscription: 'subscription-panel',
                notifications: 'notifications-panel',
                profile: 'profile-panel'
            };

            Object.keys(panelMap).forEach(function (key) {
                setPanelVisibility(panelMap[key], false);
            });

            document.querySelectorAll('.nav-btn').forEach(function (btn) {
                btn.classList.remove('active');
            });

            var activePanelName = panelMap[panel] ? panel : 'dashboard';
            setPanelVisibility(panelMap[activePanelName], true);

            var activeBtn = document.querySelector('.nav-btn[data-panel="' + activePanelName + '"]');
            if (activeBtn) {
                activeBtn.classList.add('active');
            }
        }

        function reserveTrajet(btn) {
            var config = getConfig();
            var slotKey = btn.dataset.slotKey;
            var ligneId = btn.dataset.ligneId;
            var horaireId = btn.dataset.horaireId;
            var sensKey = btn.dataset.sensKey;
            var ligne = btn.dataset.ligne;
            var sens = btn.dataset.sens;
            var heure = btn.dataset.heure;

            fetch(config.reserveUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                },
                body: JSON.stringify({
                    ligne_id: ligneId,
                    horaire_id: horaireId,
                    sens: sensKey
                })
            }).then(function (response) { return response.json(); })
                .then(function (result) {
                    if (!result.success) {
                        if (result.past_slot) {
                            alert(result.error + ' La page va se recharger pour mettre a jour l\'historique.');
                            window.location.reload();
                            return;
                        }
                        alert('Erreur: ' + result.error);
                        return;
                    }

                    var assignedBus = result.assigned_bus || '-';
                    var stateWrapper = document.createElement('div');
                    stateWrapper.className = 'reservation-state reservation-state-stack';

                    var statusBadge = document.createElement('span');
                    statusBadge.className = 'tag tag-active';
                    statusBadge.innerHTML = '<i class="fas fa-check"></i> Reservation confirmee';

                    var busInfo = document.createElement('small');
                    busInfo.className = 'reservation-bus-info';
                    busInfo.textContent = 'Bus attribue: ' + assignedBus;

                    var cancelBtn = document.createElement('button');
                    cancelBtn.className = 'btn-del';
                    cancelBtn.textContent = 'Annuler la reservation';
                    cancelBtn.dataset.slotKey = slotKey;
                    cancelBtn.dataset.ligneId = ligneId;
                    cancelBtn.dataset.horaireId = horaireId;
                    cancelBtn.dataset.ligne = ligne;
                    cancelBtn.dataset.sens = sens;
                    cancelBtn.dataset.sensKey = sensKey;
                    cancelBtn.dataset.heure = heure;
                    cancelBtn.onclick = function () { cancelReservation(cancelBtn); };

                    stateWrapper.appendChild(statusBadge);
                    stateWrapper.appendChild(busInfo);
                    stateWrapper.appendChild(cancelBtn);
                    btn.parentNode.replaceChild(stateWrapper, btn);

                    var tbody = document.getElementById('dashboard-reserved-tbody');
                    var emptyRow = document.getElementById('dashboard-reserved-empty');
                    if (emptyRow) {
                        emptyRow.remove();
                    }

                    var existingRow = document.getElementById('dashboard-row-' + slotKey);
                    var rowHtml = '<td data-label="Ligne">' + ligne + '</td><td data-label="Sens">' + sens + '</td><td data-label="Heure">' + heure + '</td><td data-label="Bus">' + assignedBus + '</td><td data-label="Statut"><span class="tag tag-active">Reservation confirmee</span></td>';
                    if (existingRow) {
                        existingRow.innerHTML = rowHtml;
                    } else if (tbody) {
                        var tr = document.createElement('tr');
                        tr.id = 'dashboard-row-' + slotKey;
                        tr.innerHTML = rowHtml;
                        tbody.appendChild(tr);
                    }
                }).catch(function (error) {
                    console.error('Error:', error);
                    alert('Une erreur est survenue lors de la reservation.');
                });
        }

        function cancelReservation(btn) {
            var config = getConfig();
            var slotKey = btn.dataset.slotKey;
            var ligneId = btn.dataset.ligneId;
            var horaireId = btn.dataset.horaireId;
            var sensKey = btn.dataset.sensKey;
            var ligne = btn.dataset.ligne;
            var sens = btn.dataset.sens;
            var heure = btn.dataset.heure;

            fetch(config.cancelReservationUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                },
                body: JSON.stringify({
                    ligne_id: ligneId,
                    horaire_id: horaireId,
                    sens: sensKey
                })
            }).then(function (response) { return response.json(); })
                .then(function (result) {
                    if (!result.success) {
                        if (result.past_slot || (result.error && result.error.indexOf('horaire est depasse') !== -1)) {
                            alert(result.error + ' La page va se recharger pour mettre a jour l\'historique.');
                            window.location.reload();
                            return;
                        }
                        alert('Erreur: ' + result.error);
                        return;
                    }

                    var reservationState = btn.closest('.reservation-state');
                    var reserveBtn = document.createElement('button');
                    reserveBtn.className = 'btn-primary btn-sm';
                    reserveBtn.innerHTML = '<i class="fas fa-plus"></i> Reserver';
                    reserveBtn.dataset.slotKey = slotKey;
                    reserveBtn.dataset.ligneId = ligneId;
                    reserveBtn.dataset.horaireId = horaireId;
                    reserveBtn.dataset.ligne = ligne;
                    reserveBtn.dataset.sens = sens;
                    reserveBtn.dataset.sensKey = sensKey;
                    reserveBtn.dataset.heure = heure;
                    reserveBtn.onclick = function () { reserveTrajet(reserveBtn); };

                    if (reservationState) {
                        reservationState.parentNode.replaceChild(reserveBtn, reservationState);
                    } else {
                        btn.parentNode.replaceChild(reserveBtn, btn);
                    }

                    var row = document.getElementById('dashboard-row-' + slotKey);
                    if (row) {
                        row.remove();
                    }

                    var tbody = document.getElementById('dashboard-reserved-tbody');
                    if (tbody && tbody.children.length === 0) {
                        var tr = document.createElement('tr');
                        tr.id = 'dashboard-reserved-empty';
                        tr.innerHTML = '<td colspan="5" class="u-inline-164">Aucun trajet reserve aujourd\'hui.</td>';
                        tbody.appendChild(tr);
                    }
                }).catch(function (error) {
                    console.error('Error:', error);
                    alert('Une erreur est survenue lors de l\'annulation.');
                });
        }

        function toggleDark() {
            if (!body) {
                return;
            }
            body.setAttribute('data-dark', body.getAttribute('data-dark') === '1' ? '0' : '1');
        }

        function logout() {
            var config = getConfig();
            if (config.logoutUrl) {
                window.location.href = config.logoutUrl;
            }
        }

        function subscribeToLine() {
            var config = getConfig();
            var ligneSelect = document.getElementById('ligne-select');
            var dateDebut = document.getElementById('date-debut');
            var dateFin = document.getElementById('date-fin');

            if (!ligneSelect.value) {
                alert('Veuillez selectionner une ligne.');
                return;
            }

            if (!dateDebut.value) {
                alert('Veuillez selectionner une date de debut.');
                return;
            }

            var data = {
                student_id: config.studentId,
                ligne_id: ligneSelect.value,
                date_debut: dateDebut.value,
                date_fin: dateFin.value || null
            };

            fetch(config.subscribeUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                },
                body: JSON.stringify(data)
            }).then(function (response) { return response.json(); })
                .then(function (result) {
                    if (!result.success) {
                        alert('Erreur: ' + result.error);
                        return;
                    }

                    alert(result.message);
                    ligneSelect.value = '';
                    dateDebut.value = '';
                    dateFin.value = '';
                    loadSubscriptionsFromServer();
                }).catch(function (error) {
                    console.error('Error:', error);
                    alert('Une erreur est survenue lors de l\'abonnement.');
                });
        }

        function loadSubscriptionsFromServer() {
            var config = getConfig();

            fetch(config.subscriptionsUrl + '?student_id=' + encodeURIComponent(config.studentId))
                .then(function (response) { return response.json(); })
                .then(function (result) {
                    if (!result.success) {
                        return;
                    }
                    subscriptions = result.subscriptions;
                    loadSubscriptions();
                }).catch(function () {
                });
        }

        function loadSubscriptions() {
            var tableBody = document.getElementById('subscriptions-table');
            if (!tableBody) {
                return;
            }

            if (!subscriptions.length) {
                tableBody.innerHTML = '<tr><td colspan="5" class="u-inline-169">Aucun abonnement actif</td></tr>';
                return;
            }

            tableBody.innerHTML = subscriptions.map(function (sub) {
                return '<tr>' +
                    '<td data-label="Ligne">' + sub.ligne + '</td>' +
                    '<td data-label="Date debut">' + sub.dateDebut + '</td>' +
                    '<td data-label="Date fin">' + sub.dateFin + '</td>' +
                    '<td data-label="Statut"><span class="tag tag-active">' + sub.statut + '</span></td>' +
                    '<td data-label="Actions"><button class="btn-del" onclick="unsubscribe(' + sub.ligne_id + ')">Se desabonner</button></td>' +
                    '</tr>';
            }).join('');
        }

        function unsubscribe(ligneId) {
            var config = getConfig();

            if (!confirm('Etes-vous sur de vouloir vous desabonner de cette ligne ?')) {
                return;
            }

            var data = {
                student_id: config.studentId,
                ligne_id: ligneId
            };

            fetch(config.unsubscribeUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                },
                body: JSON.stringify(data)
            }).then(function (response) { return response.json(); })
                .then(function (result) {
                    if (!result.success) {
                        alert('Erreur: ' + result.error);
                        return;
                    }

                    alert(result.message);
                    loadSubscriptionsFromServer();
                }).catch(function (error) {
                    console.error('Error:', error);
                    alert('Une erreur est survenue lors du desabonnement.');
                });
        }

        function closeRatingModal() {
            if (!ratingModal) {
                return;
            }
            ratingModal.classList.add('hidden');
        }

        function openRatingModal(button) {
            if (!ratingModal) {
                return false;
            }

            var trajetId = button && button.dataset ? button.dataset.trajetId : '';
            if (!trajetId) {
                alert('Trajet introuvable pour la notation.');
                return false;
            }

            document.getElementById('ratingTrajetId').value = trajetId;
            document.getElementById('ratingGeneral').value = button.dataset.currentGeneral || '';
            document.getElementById('ratingBus').value = button.dataset.currentBus || '';
            document.getElementById('ratingDriver').value = button.dataset.currentDriver || '';
            document.getElementById('ratingComment').value = '';

            ratingModal.classList.remove('hidden');
            document.getElementById('ratingGeneral').focus();
            return true;
        }

        function submitRating(event) {
            event.preventDefault();
            var config = getConfig();
            var trajetId = document.getElementById('ratingTrajetId').value;
            if (!trajetId) {
                alert('Trajet introuvable pour la notation.');
                return;
            }

            var generalRaw = document.getElementById('ratingGeneral').value;
            var busRaw = document.getElementById('ratingBus').value;
            var driverRaw = document.getElementById('ratingDriver').value;
            var commentaire = (document.getElementById('ratingComment').value || '').trim();

            var noteGenerale = Number(generalRaw);
            if (Number.isNaN(noteGenerale) || noteGenerale < 1 || noteGenerale > 5) {
                alert('La note generale doit etre un nombre entre 1 et 5.');
                return;
            }

            var noteBus = null;
            if (String(busRaw).trim() !== '') {
                noteBus = Number(busRaw);
                if (Number.isNaN(noteBus) || noteBus < 1 || noteBus > 5) {
                    alert('La note bus doit etre vide ou entre 1 et 5.');
                    return;
                }
            }

            var noteConducteur = null;
            if (String(driverRaw).trim() !== '') {
                noteConducteur = Number(driverRaw);
                if (Number.isNaN(noteConducteur) || noteConducteur < 1 || noteConducteur > 5) {
                    alert('La note conducteur doit etre vide ou entre 1 et 5.');
                    return;
                }
            }

            if (ratingSubmitBtn) {
                ratingSubmitBtn.disabled = true;
                ratingSubmitBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Enregistrement...';
            }

            fetch(config.rateUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
                },
                body: JSON.stringify({
                    trajet_id: trajetId,
                    note_generale: noteGenerale,
                    note_bus: noteBus,
                    note_conducteur: noteConducteur,
                    commentaire: commentaire
                })
            }).then(function (response) { return response.json(); })
                .then(function (result) {
                    if (!result.success) {
                        alert('Erreur: ' + (result.error || 'Notation impossible.'));
                        return;
                    }
                    alert('Evaluation enregistree avec succes.');
                    window.location.reload();
                }).catch(function (error) {
                    console.error('Error:', error);
                    alert('Une erreur est survenue lors de la notation.');
                }).finally(function () {
                    if (ratingSubmitBtn) {
                        ratingSubmitBtn.disabled = false;
                        ratingSubmitBtn.innerHTML = '<i class="fas fa-paper-plane"></i> Enregistrer l\'evaluation';
                    }
                });
        }

        function rateTrip(button) {
            if (!openRatingModal(button)) {
                return;
            }
        }

        function init() {
            subscriptions = loadInitialSubscriptions();
            loadSubscriptions();
            initHistoryFilters();

            ratingModal = document.getElementById('ratingModal');
            ratingForm = document.getElementById('ratingForm');
            ratingSubmitBtn = document.getElementById('ratingSubmitBtn');

            if (ratingForm) {
                ratingForm.addEventListener('submit', submitRating);
            }

            if (ratingModal) {
                ratingModal.addEventListener('click', function (event) {
                    if (event.target === ratingModal) {
                        closeRatingModal();
                    }
                });
            }

            document.addEventListener('keydown', function (event) {
                if (event.key === 'Escape' && ratingModal && !ratingModal.classList.contains('hidden')) {
                    closeRatingModal();
                }
            });

            // Afficher le dashboard par défaut au chargement
            showPanel('dashboard');
        }

        return {
            init: init,
            showPanel: showPanel,
            reserveTrajet: reserveTrajet,
            cancelReservation: cancelReservation,
            toggleDark: toggleDark,
            logout: logout,
            subscribeToLine: subscribeToLine,
            unsubscribe: unsubscribe,
            rateTrip: rateTrip,
            closeRatingModal: closeRatingModal
        };
    })();

    var BusTrajets = (function () {
        function openDeleteModal(actionUrl, trajetLabel) {
            var modal = document.getElementById('deleteModal');
            var form = document.getElementById('deleteModalForm');
            var detail = document.getElementById('deleteModalDetail');

            if (!modal || !form || !detail) {
                return;
            }

            form.action = actionUrl;
            detail.textContent = trajetLabel;
            modal.style.display = 'flex';
        }

        function closeDeleteModal() {
            var modal = document.getElementById('deleteModal');
            if (modal) {
                modal.style.display = 'none';
            }
        }

        return {
            openDeleteModal: openDeleteModal,
            closeDeleteModal: closeDeleteModal
        };
    })();

    var TrajetsProgrammes = (function () {
        function setToggleButtonState(button, isDark) {
            if (!button) {
                return;
            }

            button.innerHTML = isDark
                ? '<i class="fas fa-sun"></i> Mode Clair'
                : '<i class="fas fa-moon"></i> Mode Sombre';
        }

        function toggleDark(button) {
            if (!body) {
                return;
            }

            var isDark = body.getAttribute('data-dark') === '1';
            var next = isDark ? '0' : '1';

            body.setAttribute('data-dark', next);
            localStorage.setItem('darkMode', next === '1' ? 'true' : 'false');
            setToggleButtonState(button || document.querySelector('.sidebar-bottom button'), next === '1');
        }

        function logout() {
            var config = body ? body.dataset : {};
            var confirmMessage = config.logoutConfirm;

            if (confirmMessage && !window.confirm(confirmMessage)) {
                return;
            }

            if (config.logoutUrl) {
                window.location.href = config.logoutUrl;
            }
        }

        function init() {
            var darkMode = localStorage.getItem('darkMode') === 'true';
            var toggleButton = document.querySelector('.sidebar-bottom button');

            if (darkMode) {
                document.body.setAttribute('data-dark', '1');
            }

            setToggleButtonState(toggleButton, darkMode);

            if (window.location.hash === '#agenda-panel') {
                var agendaPanel = document.getElementById('agenda-panel');
                if (agendaPanel) {
                    agendaPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }

            document.querySelectorAll('.calendar-day.clickable').forEach(function (cell) {
                cell.addEventListener('click', function () {
                    var targetUrl = cell.getAttribute('data-url');
                    if (targetUrl) {
                        window.location.href = targetUrl + '#agenda-panel';
                    }
                });
            });
        }

        return {
            init: init,
            toggleDark: toggleDark,
            logout: logout
        };
    })();

    var ListeLignes = (function () {
        var isClosingAddLignePopup = false;
        var popupStateKey = 'mycous.popupState:' + window.location.pathname;

        function normalizePath(path) {
            if (!path) {
                return '/';
            }
            return path.endsWith('/') ? path : path + '/';
        }

        function savePopupState(state) {
            try {
                sessionStorage.setItem(popupStateKey, JSON.stringify(state));
            } catch (error) {
                // Ignore storage issues and keep the popup functional.
            }
        }

        function loadPopupState() {
            try {
                var rawState = sessionStorage.getItem(popupStateKey);
                return rawState ? JSON.parse(rawState) : null;
            } catch (error) {
                return null;
            }
        }

        function clearPopupState() {
            try {
                sessionStorage.removeItem(popupStateKey);
            } catch (error) {
                // Ignore storage issues.
            }
        }

        function getConfig() {
            return body ? body.dataset : {};
        }

        function getAddLigneModal() {
            return document.getElementById('addLigneModal');
        }

        function getAddLigneFrame() {
            return document.getElementById('addLigneFrame');
        }

        function updateFiltersColors() {
            var selects = document.querySelectorAll('#filtersPanel select');
            var inputs = document.querySelectorAll('#filtersPanel input[type="number"], #filtersPanel input[type="text"]');

            selects.forEach(function (select) {
                if (select.selectedIndex > 0) {
                    select.classList.add('has-selected-option');
                } else {
                    select.classList.remove('has-selected-option');
                }
            });

            inputs.forEach(function (input) {
                if (input.value !== '' && input.value.trim() !== '') {
                    input.classList.add('has-selected-option');
                } else {
                    input.classList.remove('has-selected-option');
                }
            });
        }

        function openAddLignePopup() {
            var modal = getAddLigneModal();
            var frame = getAddLigneFrame();
            var config = getConfig();
            var modalTitle = document.getElementById('addLigneModalTitle');

            if (!modal || !frame || !config.addLigneUrl) {
                return;
            }

            if (modalTitle) {
                modalTitle.innerHTML = '<i class="fas fa-route"></i> Ajouter une ligne';
            }
            frame.title = 'Formulaire Ajouter une ligne';

            // Add popup parameters to the URL
            var url = config.addLigneUrl;
            var separator = url.indexOf('?') >= 0 ? '&' : '?';
            var returnTo = encodeURIComponent(window.location.href);
            // Add cache-buster timestamp to prevent browser caching of iframe content
            var timestamp = new Date().getTime();
            frame.src = url + separator + 'popup=1&return_to=' + returnTo + '&_t=' + timestamp;
            modal.dataset.returnUrl = window.location.href;
            savePopupState({
                kind: 'add',
                title: 'Ajouter une ligne',
                iconClass: 'fas fa-route',
                url: frame.src,
                returnUrl: window.location.href
            });
            modal.classList.remove('hidden');
            document.body.style.overflow = 'hidden';
        }

        function closeAddLignePopup() {
            var modal = getAddLigneModal();
            var frame = getAddLigneFrame();

            if (!modal || !frame) {
                return;
            }

            modal.classList.add('hidden');
            modal.dataset.returnUrl = '';
            clearPopupState();
            isClosingAddLignePopup = true;
            frame.src = 'about:blank';
            document.body.style.overflow = '';
            setTimeout(function () {
                isClosingAddLignePopup = false;
            }, 0);
        }

        function openFormPopup(url, title, iconClass) {
            var modal = getAddLigneModal();
            var frame = getAddLigneFrame();
            var modalTitle = document.getElementById('addLigneModalTitle');
            if (!modal || !frame) {
                return;
            }

            if (modalTitle) {
                var icon = iconClass || 'fas fa-file-alt';
                modalTitle.innerHTML = '<i class="' + icon + '"></i> ' + (title || 'Formulaire');
            }
            frame.title = title || 'Formulaire';

            try {
                var absoluteUrl = new URL(url, window.location.origin);
                absoluteUrl.searchParams.set('popup', '1');
                absoluteUrl.searchParams.set('return_to', window.location.href);
                // Add cache-buster timestamp to prevent browser caching of iframe content
                absoluteUrl.searchParams.set('_t', new Date().getTime().toString());
                frame.src = absoluteUrl.toString();
                modal.dataset.returnUrl = window.location.href;
                savePopupState({
                    kind: 'form',
                    title: title || 'Formulaire',
                    iconClass: iconClass || 'fas fa-file-alt',
                    url: frame.src,
                    returnUrl: window.location.href
                });
            } catch (error) {
                frame.src = url;
                modal.dataset.returnUrl = window.location.href;
                savePopupState({
                    kind: 'form',
                    title: title || 'Formulaire',
                    iconClass: iconClass || 'fas fa-file-alt',
                    url: url,
                    returnUrl: window.location.href
                });
            }

            modal.classList.remove('hidden');
            document.body.style.overflow = 'hidden';
        }

        function setupFiltersPanel() {
            var toggleBtn = document.getElementById('toggleFilters');
            var filtersPanel = document.getElementById('filtersPanel');
            var clearBtn = document.getElementById('clearFilters');

            if (!toggleBtn || !filtersPanel || !clearBtn) {
                return;
            }

            toggleBtn.addEventListener('click', function () {
                var isHidden = filtersPanel.classList.contains('hidden');
                filtersPanel.classList.toggle('hidden', !isHidden);
                toggleBtn.classList.toggle('active', isHidden);
            });

            clearBtn.addEventListener('click', function () {
                var form = document.querySelector('.filter-form');
                if (!form) {
                    return;
                }

                form.querySelectorAll('select').forEach(function (select) {
                    select.selectedIndex = 0;
                });

                form.querySelectorAll('input').forEach(function (input) {
                    input.value = '';
                });

                updateFiltersColors();
            });

            var hasActiveFilters = document.body.dataset.hasFilters === '1';
            if (hasActiveFilters) {
                filtersPanel.classList.remove('hidden');
                toggleBtn.classList.add('active');
            }
        }

        function init() {
            var modal = getAddLigneModal();
            var frame = getAddLigneFrame();

            if (modal && frame && frame.dataset.boundLoad !== '1') {
                frame.dataset.boundLoad = '1';
                frame.addEventListener('load', function () {
                    if (isClosingAddLignePopup) {
                        return;
                    }

                    var returnUrl = modal.dataset.returnUrl || '';
                    if (!returnUrl) {
                        return;
                    }

                    try {
                        var targetPath = normalizePath(new URL(returnUrl, window.location.origin).pathname);
                        var currentPath = normalizePath(frame.contentWindow.location.pathname);

                        if (targetPath === currentPath) {
                            closeAddLignePopup();
                            if (window.location.href === returnUrl) {
                                window.location.reload();
                            } else {
                                window.location.href = returnUrl;
                            }
                        }
                    } catch (error) {
                        // Ignore cross-origin or URL parsing errors.
                    }
                });
            }

            var savedState = loadPopupState();
            if (savedState && savedState.url && modal.classList.contains('hidden')) {
                if (savedState.kind === 'add') {
                    openAddLignePopup();
                } else {
                    openFormPopup(savedState.url, savedState.title, savedState.iconClass);
                }
            }

            updateFiltersColors();
            setupFiltersPanel();

            document.querySelectorAll('#filtersPanel select, #filtersPanel input[type="number"], #filtersPanel input[type="text"]').forEach(function (field) {
                field.addEventListener('change', updateFiltersColors);
                field.addEventListener('input', updateFiltersColors);
            });
        }

        return {
            init: init,
            openAddLignePopup: openAddLignePopup,
            closeAddLignePopup: closeAddLignePopup,
            openFormPopup: openFormPopup,
            updateFiltersColors: updateFiltersColors
        };
    })();

    var LigneForm = (function () {
        function init() {
            var addBtn = document.getElementById('addHoraireRowBtn');
            var rowsContainer = document.getElementById('horaireRowsContainer');
            var emptyFormTemplate = document.getElementById('horaireEmptyFormTemplate');
            var totalFormsInput = document.getElementById('id_horaires-TOTAL_FORMS');
            var formElement = rowsContainer ? rowsContainer.closest('form') : null;

            if (!rowsContainer || !totalFormsInput) {
                return;
            }

            function hasObjectId(row) {
                var idField = row.querySelector('input[type="hidden"][name$="-id"]');
                return Boolean(idField && idField.value);
            }

            function isEffectivelyEmpty(row) {
                var dayField = row.querySelector('select[name$="-jour_semaine"]');
                var departField = row.querySelector('input[name$="-heure_depart"]');

                var hasDay = Boolean(dayField && dayField.value);
                var hasDepart = Boolean(departField && departField.value);

                return !hasObjectId(row) && !hasDay && !hasDepart;
            }

            function compactInitialRows() {
                var rows = Array.from(rowsContainer.querySelectorAll('[data-form-row]'));
                var emptyRows = rows.filter(isEffectivelyEmpty);

                if (emptyRows.length <= 1) {
                    return;
                }

                emptyRows.slice(1).forEach(function (row) {
                    row.remove();
                });

                var remainingRows = rowsContainer.querySelectorAll('[data-form-row]').length;
                totalFormsInput.value = String(remainingRows);
            }

            function refreshRowNumbers() {
                var visibleIndex = 1;
                rowsContainer.querySelectorAll('[data-form-row]').forEach(function (row) {
                    if (row.style.display === 'none') {
                        return;
                    }

                    var pairMarker = row.querySelector('[data-row-number]');
                    if (pairMarker) {
                        pairMarker.textContent = String(Math.ceil(visibleIndex / 2));
                    }

                    var sensField = row.querySelector('select[name$="-sens"]');
                    var sensPill = row.querySelector('[data-sens-pill]');
                    var departLabel = row.querySelector('[data-depart-label]');
                    var sensValue = sensField ? sensField.value : '';
                    var sensLabel = sensValue === 'retour' ? 'Retour' : 'Aller';

                    if (sensPill) {
                        sensPill.textContent = sensLabel;
                    }
                    if (departLabel) {
                        departLabel.textContent = sensLabel === 'Retour' ? 'Heure de départ retour' : 'Heure de départ aller';
                    }

                    visibleIndex += 1;
                });
            }

            function setExpandedRow(targetRow) {
                rowsContainer.querySelectorAll('[data-form-row]').forEach(function (row) {
                    var toggle = row.querySelector('[data-toggle-row]');
                    var isTarget = row === targetRow && row.style.display !== 'none';

                    row.classList.toggle('is-expanded', isTarget);
                    if (toggle) {
                        toggle.setAttribute('aria-expanded', isTarget ? 'true' : 'false');
                        var icon = toggle.querySelector('.horaire-toggle-icon');
                        if (icon) {
                            icon.textContent = isTarget ? '-' : '+';
                        }
                    }
                });
            }

            function expandFirstVisibleRow() {
                var firstVisible = Array.from(rowsContainer.querySelectorAll('[data-form-row]')).find(function (row) {
                    return row.style.display !== 'none';
                });

                if (firstVisible) {
                    setExpandedRow(firstVisible);
                }
            }

            function expandFirstRowWithErrors() {
                var rowWithError = Array.from(rowsContainer.querySelectorAll('[data-form-row]')).find(function (row) {
                    if (row.style.display === 'none') {
                        return false;
                    }
                    return Boolean(row.querySelector('.error-text'));
                });

                if (rowWithError) {
                    setExpandedRow(rowWithError);
                    return true;
                }
                return false;
            }

            function bindAccordionToggles(scope) {
                scope.querySelectorAll('[data-toggle-row]').forEach(function (toggleBtn) {
                    if (toggleBtn.dataset.bound === '1') {
                        return;
                    }

                    toggleBtn.dataset.bound = '1';
                    toggleBtn.addEventListener('click', function () {
                        var row = toggleBtn.closest('[data-form-row]');
                        if (!row) {
                            return;
                        }

                        var alreadyExpanded = row.classList.contains('is-expanded');
                        if (alreadyExpanded) {
                            setExpandedRow(null);
                        } else {
                            setExpandedRow(row);
                        }
                    });
                });
            }

            function markRowForDeletion(row) {
                var deleteCheckbox = row.querySelector('input[type="checkbox"][name$="-DELETE"]');
                if (deleteCheckbox) {
                    deleteCheckbox.checked = true;
                }

                row.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]), select, textarea').forEach(function (field) {
                    field.required = false;
                    field.disabled = true;
                });

                row.style.display = 'none';
                refreshRowNumbers();
                expandFirstVisibleRow();
            }

            function normalizeDeletedRowsBeforeSubmit() {
                rowsContainer.querySelectorAll('[data-form-row]').forEach(function (row) {
                    var deleteCheckbox = row.querySelector('input[type="checkbox"][name$="-DELETE"]');
                    if (!deleteCheckbox) {
                        return;
                    }

                    if (row.style.display === 'none') {
                        deleteCheckbox.checked = true;
                    }

                    if (deleteCheckbox.checked) {
                        row.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]), select, textarea').forEach(function (field) {
                            field.required = false;
                            field.disabled = true;
                        });
                    }
                });
            }

            function bindRemoveButtons(scope) {
                scope.querySelectorAll('[data-remove-horaire-row]').forEach(function (btn) {
                    if (btn.dataset.bound === '1') {
                        return;
                    }

                    btn.dataset.bound = '1';
                    btn.addEventListener('click', function () {
                        var row = btn.closest('[data-form-row]');
                        if (!row) {
                            return;
                        }
                        markRowForDeletion(row);
                    });
                });
            }

            function bindSensSelectors(scope) {
                scope.querySelectorAll('select[name$="-sens"]').forEach(function (select) {
                    if (select.dataset.bound === '1') {
                        return;
                    }

                    select.dataset.bound = '1';
                    select.addEventListener('change', refreshRowNumbers);
                });
            }

            compactInitialRows();
            bindRemoveButtons(document);
            bindAccordionToggles(document);
            bindSensSelectors(document);
            refreshRowNumbers();
            if (!expandFirstRowWithErrors()) {
                expandFirstVisibleRow();
            }

            if (formElement && formElement.dataset.horairesNormalizeBound !== '1') {
                formElement.dataset.horairesNormalizeBound = '1';
                formElement.addEventListener('submit', normalizeDeletedRowsBeforeSubmit);
            }

            if (addBtn && emptyFormTemplate) {
                function appendPairRow(sensValue) {
                    var nextIndex = Number(totalFormsInput.value);
                    var html = emptyFormTemplate.innerHTML.replaceAll('__prefix__', String(nextIndex));
                    var tempWrapper = document.createElement('div');
                    tempWrapper.innerHTML = html.trim();
                    var newRow = tempWrapper.firstElementChild;

                    if (!newRow) {
                        return null;
                    }

                    var deleteCheckbox = newRow.querySelector('input[type="checkbox"][name$="-DELETE"]');
                    if (deleteCheckbox) {
                        deleteCheckbox.checked = false;
                    }

                    var sensField = newRow.querySelector('select[name$="-sens"]');
                    if (sensField && sensValue) {
                        sensField.value = sensValue;
                    }

                    rowsContainer.appendChild(newRow);
                    totalFormsInput.value = String(nextIndex + 1);
                    bindRemoveButtons(newRow);
                    bindAccordionToggles(newRow);
                    bindSensSelectors(newRow);
                    return newRow;
                }

                addBtn.addEventListener('click', function () {
                    var allerRow = appendPairRow('aller');
                    var retourRow = appendPairRow('retour');
                    refreshRowNumbers();
                    setExpandedRow(retourRow || allerRow);
                });
            }
        }

        return { init: init };
    })();

    var StationFormset = (function () {
        function init() {
            var addBtn = document.getElementById('addStationRowBtn');
            var rowsContainer = document.getElementById('stationRowsContainer');
            var emptyFormTemplate = document.getElementById('stationEmptyFormTemplate');
            var totalFormsInput = document.getElementById('id_stations-TOTAL_FORMS');
            var nomLigneInput = document.getElementById('id_nom_ligne');
            var formElement = rowsContainer ? rowsContainer.closest('form') : null;

            if (!rowsContainer || !totalFormsInput) {
                return;
            }

            // Keep the exact behavior from the former inline script.
            var lastAutoValue = nomLigneInput ? nomLigneInput.value.trim() : '';
            var userOverride = false;

            function getVisibleRows() {
                return Array.from(rowsContainer.querySelectorAll('[data-form-row]')).filter(function (row) {
                    var del = row.querySelector('input[type="checkbox"][name$="-DELETE"]');
                    return !(del && del.checked);
                });
            }

            function autoGenerateName() {
                if (!nomLigneInput || userOverride) {
                    return;
                }

                var rows = getVisibleRows();
                var pairs = [];

                rows.forEach(function (row) {
                    var stationSel = row.querySelector('select[name$="-station"]');
                    var ordreInp = row.querySelector('input[name$="-ordre"]');
                    if (!stationSel || !ordreInp) {
                        return;
                    }

                    var stationVal = stationSel.value;
                    var ordreVal = parseInt(ordreInp.value, 10);
                    if (!stationVal || isNaN(ordreVal)) {
                        return;
                    }

                    var selectedOption = stationSel.options[stationSel.selectedIndex];
                    var stationText = selectedOption ? selectedOption.text.trim() : '';
                    if (stationText && stationText !== '---------') {
                        pairs.push({ ordre: ordreVal, name: stationText });
                    }
                });

                if (pairs.length < 2) {
                    return;
                }

                pairs.sort(function (a, b) {
                    return a.ordre - b.ordre;
                });

                var depart = pairs[0].name;
                var arrivee = pairs[pairs.length - 1].name;
                var generated = depart + ' ↔ ' + arrivee;

                nomLigneInput.value = generated;
                lastAutoValue = generated;
            }

            if (nomLigneInput) {
                nomLigneInput.addEventListener('input', function () {
                    if (this.value.trim() === '') {
                        userOverride = false;
                        lastAutoValue = '';
                        autoGenerateName();
                    } else if (this.value.trim() !== lastAutoValue) {
                        userOverride = true;
                    }
                });
            }

            rowsContainer.addEventListener('change', function (event) {
                if (event.target.matches('select[name$="-station"]') ||
                    event.target.matches('input[name$="-ordre"]') ||
                    event.target.matches('input[type="checkbox"][name$="-DELETE"]')) {
                    autoGenerateName();
                }
            });

            rowsContainer.addEventListener('input', function (event) {
                if (event.target.matches('input[name$="-ordre"]')) {
                    autoGenerateName();
                }
            });

            if (addBtn) {
                addBtn.addEventListener('click', function () {
                    setTimeout(autoGenerateName, 50);
                });
            }

            function hasObjectId(row) {
                var idField = row.querySelector('input[type="hidden"][name$="-id"]');
                return Boolean(idField && idField.value);
            }

            function isEffectivelyEmpty(row) {
                var stationField = row.querySelector('select[name$="-station"]');
                var ordreField = row.querySelector('input[name$="-ordre"]');

                var hasStation = Boolean(stationField && stationField.value);
                var hasOrdre = Boolean(ordreField && ordreField.value);

                return !hasObjectId(row) && !hasStation && !hasOrdre;
            }

            function compactInitialRows() {
                var rows = Array.from(rowsContainer.querySelectorAll('[data-form-row]'));
                var emptyRows = rows.filter(isEffectivelyEmpty);

                if (emptyRows.length <= 1) {
                    return;
                }

                emptyRows.slice(1).forEach(function (row) {
                    row.remove();
                });

                var remainingRows = rowsContainer.querySelectorAll('[data-form-row]').length;
                totalFormsInput.value = String(remainingRows);
            }

            function markRowForDeletion(row) {
                var deleteCheckbox = row.querySelector('input[type="checkbox"][name$="-DELETE"]');
                if (deleteCheckbox) {
                    deleteCheckbox.checked = true;
                }

                row.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]), select, textarea').forEach(function (field) {
                    field.required = false;
                    field.disabled = true;
                });

                row.style.display = 'none';
            }

            function normalizeDeletedRowsBeforeSubmit() {
                rowsContainer.querySelectorAll('[data-form-row]').forEach(function (row) {
                    var deleteCheckbox = row.querySelector('input[type="checkbox"][name$="-DELETE"]');
                    if (!deleteCheckbox) {
                        return;
                    }

                    if (row.style.display === 'none') {
                        deleteCheckbox.checked = true;
                    }

                    if (deleteCheckbox.checked) {
                        row.querySelectorAll('input:not([type="hidden"]):not([type="checkbox"]), select, textarea').forEach(function (field) {
                            field.required = false;
                            field.disabled = true;
                        });
                    }
                });
            }

            function bindRemoveButtons(scope) {
                scope.querySelectorAll('[data-remove-station-row]').forEach(function (btn) {
                    if (btn.dataset.bound === '1') {
                        return;
                    }

                    btn.dataset.bound = '1';
                    btn.addEventListener('click', function () {
                        var row = btn.closest('[data-form-row]');
                        if (!row) {
                            return;
                        }
                        markRowForDeletion(row);
                        autoGenerateName();
                    });
                });
            }

            compactInitialRows();
            bindRemoveButtons(document);
            autoGenerateName();

            if (formElement && formElement.dataset.stationsNormalizeBound !== '1') {
                formElement.dataset.stationsNormalizeBound = '1';
                formElement.addEventListener('submit', normalizeDeletedRowsBeforeSubmit);
            }

            if (addBtn && emptyFormTemplate) {
                addBtn.addEventListener('click', function () {
                    var nextIndex = Number(totalFormsInput.value);
                    var html = emptyFormTemplate.innerHTML.replaceAll('__prefix__', String(nextIndex));
                    var tempWrapper = document.createElement('div');
                    tempWrapper.innerHTML = html.trim();
                    var newRow = tempWrapper.firstElementChild;

                    if (!newRow) {
                        return;
                    }

                    var deleteCheckbox = newRow.querySelector('input[type="checkbox"][name$="-DELETE"]');
                    if (deleteCheckbox) {
                        deleteCheckbox.checked = false;
                    }

                    rowsContainer.appendChild(newRow);
                    totalFormsInput.value = String(nextIndex + 1);
                    bindRemoveButtons(newRow);
                });
            }
        }

        return { init: init };
    })();

    var FilterHighlight = (function () {
        var initialized = false;

        function hasValue(field) {
            if (!field || field.disabled) {
                return false;
            }

            if (field.tagName === 'SELECT') {
                return (field.value || '').trim() !== '';
            }

            var type = (field.type || '').toLowerCase();
            if (type === 'hidden' || type === 'submit' || type === 'button' || type === 'reset') {
                return false;
            }

            if (type === 'checkbox' || type === 'radio') {
                return field.checked;
            }

            return (field.value || '').trim() !== '';
        }

        function paint(field, active) {
            if (!field || field.disabled) {
                return;
            }

            if (active) {
                field.classList.add('has-selected-option');
                field.style.backgroundColor = 'var(--brand)';
                field.style.color = '#ffffff';
                field.style.borderColor = 'var(--brand)';
                if (field.tagName === 'INPUT' || field.tagName === 'TEXTAREA') {
                    field.style.caretColor = '#ffffff';
                }
                return;
            }

            field.classList.remove('has-selected-option');
            field.style.backgroundColor = '';
            field.style.color = '';
            field.style.borderColor = '';
            field.style.caretColor = '';
        }

        function getFilterFields(scope) {
            return scope.querySelectorAll(
                'form[method="get"] select, ' +
                'form[method="get"] input, ' +
                'form[method="get"] textarea'
            );
        }

        function refreshFilterHighlights(scope) {
            var root = scope || document;
            getFilterFields(root).forEach(function (field) {
                paint(field, hasValue(field));
            });
        }

        function handleFieldEvent(event) {
            var field = event.target;
            if (!field || !field.closest('form[method="get"]')) {
                return;
            }
            paint(field, hasValue(field));
        }

        function init() {
            if (initialized) {
                return;
            }
            initialized = true;
            refreshFilterHighlights(document);
            document.addEventListener('change', handleFieldEvent);
            document.addEventListener('input', handleFieldEvent);
        }

        return {
            init: init,
            refresh: refreshFilterHighlights
        };
    })();

    var RemplissageBus = (function () {
        function init() {
            document.querySelectorAll('.occupancy-fill[data-rate]').forEach(function (bar) {
                var rate = Number(bar.dataset.rate);

                if (Number.isNaN(rate)) {
                    bar.style.width = '0%';
                    return;
                }

                var clamped = Math.max(0, Math.min(100, rate));
                bar.style.width = clamped + '%';
            });
        }

        return { init: init };
    })();

    var DriverHome = (function () {
        var actionModalState = {
            mode: '',
            trajetId: '',
            rowRef: null,
            submitHandler: null
        };

        function getConfig() {
            return body ? body.dataset : {};
        }

        function csrfToken() {
            var token = document.querySelector('[name=csrfmiddlewaretoken]');
            return token ? token.value : '';
        }

        function notify(message) {
            window.alert(message);
        }

        function getActionModalNodes() {
            return {
                modal: document.getElementById('driver-action-modal'),
                title: document.getElementById('driver-action-title'),
                closeBtn: document.getElementById('driver-action-close'),
                cancelBtn: document.getElementById('driver-action-cancel'),
                submitBtn: document.getElementById('driver-action-submit'),
                retardFields: document.getElementById('driver-action-retard-fields'),
                incidentFields: document.getElementById('driver-action-incident-fields'),
                retardInput: document.getElementById('driver-retard-minutes'),
                incidentTypeInput: document.getElementById('driver-incident-type'),
                incidentDescriptionInput: document.getElementById('driver-incident-description')
            };
        }

        function closeActionModal() {
            var nodes = getActionModalNodes();
            if (!nodes.modal) {
                return;
            }
            nodes.modal.classList.remove('is-open');
            nodes.modal.setAttribute('aria-hidden', 'true');
            actionModalState.submitHandler = null;
        }

        function openActionModal(mode, options) {
            var nodes = getActionModalNodes();
            if (!nodes.modal) {
                return;
            }

            actionModalState.mode = mode;
            actionModalState.trajetId = options.trajetId || '';
            actionModalState.rowRef = options.rowRef || null;

            if (mode === 'retard') {
                nodes.title.textContent = 'Declarer un retard';
                nodes.retardFields.style.display = 'block';
                nodes.incidentFields.style.display = 'none';
                nodes.submitBtn.textContent = 'Enregistrer';
                nodes.retardInput.value = String(options.initialMinutes || 0);
                actionModalState.submitHandler = function () {
                    var minutes = Number(nodes.retardInput.value);
                    if (Number.isNaN(minutes) || minutes < 0 || minutes > 240) {
                        notify('Veuillez saisir un retard valide entre 0 et 240 minutes.');
                        return;
                    }

                    fetch(getConfig().driverRetardUrl, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken()
                        },
                        body: JSON.stringify({ trajet_id: actionModalState.trajetId, retard_minutes: minutes })
                    }).then(function (response) { return response.json(); })
                        .then(function (result) {
                            if (!result.success) {
                                notify(result.error || 'Impossible de declarer le retard.');
                                return;
                            }
                            if (actionModalState.rowRef) {
                                var cell = actionModalState.rowRef.querySelector('.js-retard-cell');
                                if (cell) {
                                    cell.textContent = result.retard_minutes + ' min';
                                }
                            }
                            closeActionModal();
                            notify('Retard enregistre.');
                        }).catch(function () {
                            notify('Erreur reseau pendant la declaration du retard.');
                        });
                };
            } else {
                nodes.title.textContent = 'Signaler un incident';
                nodes.retardFields.style.display = 'none';
                nodes.incidentFields.style.display = 'block';
                nodes.submitBtn.textContent = 'Signaler';
                nodes.incidentTypeInput.value = options.initialType || 'Technique';
                nodes.incidentDescriptionInput.value = '';
                actionModalState.submitHandler = function () {
                    var typeIncident = String(nodes.incidentTypeInput.value || '').trim();
                    if (!typeIncident) {
                        notify('Le type d\'incident est obligatoire.');
                        return;
                    }
                    var description = String(nodes.incidentDescriptionInput.value || '').trim();

                    fetch(getConfig().driverIncidentUrl, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken()
                        },
                        body: JSON.stringify({
                            trajet_id: actionModalState.trajetId,
                            type_incident: typeIncident,
                            description: description
                        })
                    }).then(function (response) { return response.json(); })
                        .then(function (result) {
                            if (!result.success) {
                                notify(result.error || 'Impossible de signaler l\'incident.');
                                return;
                            }
                            closeActionModal();
                            notify('Incident signale avec succes.');
                        }).catch(function () {
                            notify('Erreur reseau pendant le signalement.');
                        });
                };
            }

            nodes.modal.classList.add('is-open');
            nodes.modal.setAttribute('aria-hidden', 'false');
            if (mode === 'retard') {
                nodes.retardInput.focus();
            } else {
                nodes.incidentTypeInput.focus();
            }
        }

        function bindActionModal() {
            var nodes = getActionModalNodes();
            if (!nodes.modal || !nodes.submitBtn) {
                return;
            }

            nodes.closeBtn.addEventListener('click', closeActionModal);
            nodes.cancelBtn.addEventListener('click', closeActionModal);
            nodes.submitBtn.addEventListener('click', function () {
                if (typeof actionModalState.submitHandler === 'function') {
                    actionModalState.submitHandler();
                }
            });
            nodes.modal.addEventListener('click', function (event) {
                if (event.target === nodes.modal) {
                    closeActionModal();
                }
            });
            document.addEventListener('keydown', function (event) {
                if (event.key === 'Escape' && nodes.modal.classList.contains('is-open')) {
                    closeActionModal();
                }
            });
        }

        function updateRowStatus(row, statusLabel, statusClass, statusKey) {
            var chip = row.querySelector('.js-status-chip');
            if (chip) {
                chip.className = 'chip js-status-chip ' + statusClass;
                chip.textContent = statusLabel;
            }

            var btnDepart = row.querySelector('.js-driver-status[data-action="depart"]');
            var btnArrivee = row.querySelector('.js-driver-status[data-action="arrivee"]');
            if (btnDepart) {
                btnDepart.disabled = statusKey !== 'a_venir' && statusKey !== 'en_attente';
            }
            if (btnArrivee) {
                btnArrivee.disabled = statusKey !== 'en_route';
            }
        }

        function bindActionHandlers() {
            var main = document.querySelector('main');
            if (!main) {
                return;
            }

            main.addEventListener('click', function (event) {
                var actionBtn = event.target.closest('.js-driver-status');
                if (actionBtn) {
                    var rowStatus = actionBtn.closest('tr[data-trajet-id]');
                    var trajetIdStatus = rowStatus ? rowStatus.dataset.trajetId : actionBtn.dataset.trajetId;
                    if (!trajetIdStatus) {
                        return;
                    }

                    var action = actionBtn.dataset.action;
                    var configStatus = getConfig();

                    fetch(configStatus.driverStatusUrl, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken()
                        },
                        body: JSON.stringify({ trajet_id: trajetIdStatus, action: action })
                    }).then(function (response) { return response.json(); })
                        .then(function (result) {
                            if (!result.success) {
                                notify(result.error || 'Operation impossible.');
                                return;
                            }
                            if (rowStatus) {
                                updateRowStatus(rowStatus, result.status_label, result.status_class, result.status_key);
                            }
                        }).catch(function () {
                            notify('Erreur reseau pendant la mise a jour du statut.');
                        });
                    return;
                }

                var retardBtn = event.target.closest('.js-driver-retard');
                if (retardBtn) {
                    var rowRetard = retardBtn.closest('tr[data-trajet-id]');
                    var trajetIdRetard = rowRetard ? rowRetard.dataset.trajetId : retardBtn.dataset.trajetId;
                    if (!trajetIdRetard) {
                        return;
                    }

                    openActionModal('retard', {
                        trajetId: trajetIdRetard,
                        rowRef: rowRetard,
                        initialMinutes: rowRetard ? Number((rowRetard.querySelector('.js-retard-cell') || {}).textContent || 0) : 0
                    });
                    return;
                }

                var incidentBtn = event.target.closest('.js-driver-incident');
                if (incidentBtn) {
                    var rowIncident = incidentBtn.closest('tr[data-trajet-id]');
                    var trajetIdIncident = rowIncident ? rowIncident.dataset.trajetId : incidentBtn.dataset.trajetId;
                    if (!trajetIdIncident) {
                        return;
                    }

                    openActionModal('incident', {
                        trajetId: trajetIdIncident,
                        rowRef: rowIncident,
                        initialType: 'Technique'
                    });
                }
            });
        }

        function showDriverPanel(panelName, button) {
            var panels = {
                dashboard: document.getElementById('driver-dashboard-panel'),
                trajets: document.getElementById('driver-trajets-panel'),
                carte: document.getElementById('driver-carte-panel'),
                affectations: document.getElementById('driver-affectations-panel'),
                historique: document.getElementById('driver-historique-panel'),
                profil: document.getElementById('driver-profil-panel')
            };

            Object.keys(panels).forEach(function (key) {
                var panel = panels[key];
                if (!panel) {
                    return;
                }
                panel.classList.remove('panel-visible');
                panel.classList.add('panel-hidden');
                panel.style.display = 'none';
            });

            if (panels[panelName]) {
                panels[panelName].classList.remove('panel-hidden');
                panels[panelName].classList.add('panel-visible');
                panels[panelName].style.display = 'block';
            }

            document.querySelectorAll('aside .nav-btn').forEach(function (navButton) {
                navButton.classList.remove('active');
            });

            if (button) {
                button.classList.add('active');
            }

            if (panelName === 'carte' && window.routeMap) {
                setTimeout(function () {
                    window.routeMap.invalidateSize();
                }, 150);
            }
        }

        function initRouteMap() {
            if (typeof L === 'undefined') {
                return;
            }
            var mapContainer = document.getElementById('route-map');
            if (!mapContainer || window.routeMap) {
                return;
            }

            window.routeMap = L.map('route-map').setView([36.8065, 10.1815], 11);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; OpenStreetMap contributors',
                maxZoom: 19
            }).addTo(window.routeMap);
            window.routeMarkers = [];
            window.routeLayer = null;
        }

        function clearRoute() {
            if (!window.routeMap) {
                return;
            }
            if (window.routeLayer) {
                window.routeMap.removeLayer(window.routeLayer);
                window.routeLayer = null;
            }
            if (window.routeMarkers && window.routeMarkers.length) {
                window.routeMarkers.forEach(function (marker) {
                    window.routeMap.removeLayer(marker);
                });
                window.routeMarkers = [];
            }
        }

        function showRouteDetails(distanceText, durationText, departName, arriveeName, lineDistanceKm) {
            var info = document.getElementById('route-info');
            if (!info) {
                return;
            }
            var details = '<strong>Départ :</strong> ' + departName + '<br>' +
                '<strong>Arrivée :</strong> ' + arriveeName + '<br>' +
                '<strong>Distance itinéraire (route) :</strong> ' + distanceText + '<br>' +
                '<strong>Durée estimée :</strong> ' + durationText;
            if (lineDistanceKm && String(lineDistanceKm).trim() !== '') {
                details += '<br><strong>Distance ligne (référence) :</strong> ' + lineDistanceKm + ' km';
            }
            info.innerHTML = details;
        }

        function drawRouteOnMap(routeGeojson, startLatLng, endLatLng) {
            if (!window.routeMap) {
                return;
            }
            clearRoute();
            window.routeLayer = L.geoJSON(routeGeojson, {
                style: { color: '#2563eb', weight: 6, opacity: 0.85 }
            }).addTo(window.routeMap);
            var startMarker = L.marker(startLatLng).addTo(window.routeMap).bindPopup('Départ');
            var endMarker = L.marker(endLatLng).addTo(window.routeMap).bindPopup('Arrivée');
            window.routeMarkers.push(startMarker, endMarker);
            window.routeMap.fitBounds(window.routeLayer.getBounds(), { padding: [32, 32] });
        }

        function calculateRoute() {
            var select = document.getElementById('route-select');
            if (!select) {
                return;
            }
            var selected = select.options[select.selectedIndex];
            if (!selected || !selected.value) {
                alert('Veuillez choisir un trajet valide.');
                return;
            }

            var latDepart = selected.getAttribute('data-lat-depart');
            var lngDepart = selected.getAttribute('data-lng-depart');
            var latArrivee = selected.getAttribute('data-lat-arrivee');
            var lngArrivee = selected.getAttribute('data-lng-arrivee');
            var departNom = selected.getAttribute('data-depart-nom') || 'Départ';
            var arriveeNom = selected.getAttribute('data-arrivee-nom') || 'Arrivée';
            var waypointsRaw = selected.getAttribute('data-waypoints') || '[]';
            var lineDistanceKm = selected.getAttribute('data-line-distance') || '';

            if (!latDepart || !lngDepart || !latArrivee || !lngArrivee) {
                alert("Coordonnées GPS de départ ou d'arrivée manquantes pour ce trajet.");
                return;
            }

            var coordinates = [];
            try {
                var waypoints = JSON.parse(waypointsRaw);
                if (Array.isArray(waypoints) && waypoints.length >= 2) {
                    waypoints.forEach(function (wpt) {
                        if (wpt && wpt.lng != null && wpt.lat != null) {
                            coordinates.push(wpt.lng + ',' + wpt.lat);
                        }
                    });
                }
            } catch (e) {
                coordinates = [];
            }

            if (coordinates.length < 2) {
                coordinates = [
                    lngDepart + ',' + latDepart,
                    lngArrivee + ',' + latArrivee
                ];
            }

            var url = 'https://router.project-osrm.org/route/v1/driving/' +
                coordinates.join(';') +
                '?overview=full&geometries=geojson';

            fetch(url)
                .then(function (response) { return response.json(); })
                .then(function (data) {
                    if (!data.routes || !data.routes.length) {
                        throw new Error('Aucun itinéraire trouvé.');
                    }
                    var route = data.routes[0];
                    var geojson = route.geometry;
                    var startParts = coordinates[0].split(',');
                    var endParts = coordinates[coordinates.length - 1].split(',');
                    drawRouteOnMap(
                        geojson,
                        [parseFloat(startParts[1]), parseFloat(startParts[0])],
                        [parseFloat(endParts[1]), parseFloat(endParts[0])]
                    );
                    showRouteDetails(
                        route.distance ? (route.distance / 1000).toFixed(1) + ' km' : 'N/A',
                        route.duration ? Math.ceil(route.duration / 60) + ' min' : 'N/A',
                        departNom,
                        arriveeNom,
                        lineDistanceKm
                    );

                    var config = getConfig();
                    if (config.driverSaveRouteDistanceUrl && route.distance) {
                        fetch(config.driverSaveRouteDistanceUrl, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': csrfToken()
                            },
                            body: JSON.stringify({
                                trajet_id: selected.value,
                                route_distance_km: route.distance / 1000
                            })
                        }).catch(function () {
                            // Ne pas bloquer l'affichage de l'itinéraire si la sauvegarde échoue.
                        });
                    }
                })
                .catch(function (error) {
                    var info = document.getElementById('route-info');
                    if (info) {
                        info.innerHTML = 'Impossible de calculer l\'itinéraire : ' + error.message;
                    }
                });
        }

        function init() {
            var params = new URLSearchParams(window.location.search);
            var panelName = params.get('panel');
            if (!panelName) {
                if (params.has('cal_day') || params.has('cal_date')) {
                    panelName = 'trajets';
                } else {
                    panelName = 'dashboard';
                }
            }
            if (!['dashboard', 'trajets', 'carte', 'affectations', 'historique', 'profil'].includes(panelName)) {
                panelName = 'dashboard';
            }

            var navButton = document.querySelector('aside .nav-btn[data-panel="' + panelName + '"]') || document.querySelector('aside .nav-btn');
            showDriverPanel(panelName, navButton);

            initRouteMap();

            if (window.location.hash === '#agenda-panel' || params.has('cal_day')) {
                var agendaPanel = document.getElementById('agenda-panel');
                if (agendaPanel) {
                    agendaPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }

            document.querySelectorAll('.driver-calendar-day.clickable').forEach(function (cell) {
                cell.addEventListener('click', function () {
                    var targetUrl = cell.getAttribute('data-url');
                    if (targetUrl) {
                        window.location.href = targetUrl + '#agenda-panel';
                    }
                });
            });

            var calculateButton = document.getElementById('route-calc-button');
            if (calculateButton) {
                calculateButton.addEventListener('click', calculateRoute);
            }

            bindActionModal();
            bindActionHandlers();
        }

        return {
            init: init,
            showDriverPanel: showDriverPanel
        };
    })();

    // Wrapper global pour showDriverPanel (appelé depuis les onclick du template)
    window.showDriverPanel = function (panelName, button) {
        if (DriverHome) {
            DriverHome.showDriverPanel(panelName, button);
        }
    };

    // Wrapper global pour logout (appelé depuis les onclick du template)
    window.logout = function () {
        var logoutUrl = document.body.getAttribute('data-logout-url');
        var csrfToken = document.querySelector('[name=csrfmiddlewaretoken]');
        
        if (!logoutUrl) {
            console.error('Logout URL not configured');
            return;
        }

        fetch(logoutUrl, {
            method: 'POST',
            headers: {
                'X-CSRFToken': csrfToken ? csrfToken.value : '',
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: csrfToken ? 'csrfmiddlewaretoken=' + encodeURIComponent(csrfToken.value) : ''
        }).then(function () {
            var loginUrl = document.body.getAttribute('data-login-url');
            if (loginUrl) {
                window.location.href = loginUrl;
            } else {
                window.location.href = '/';
            }
        }).catch(function (err) {
            console.error('Logout failed:', err);
            alert('Erreur lors de la déconnexion');
        });
    };

    var DeleteAffectationModal = (function () {
        function init() {
            var form = document.getElementById('delete-affectation-form');
            if (!form) {
                return;
            }

            var inModal = window.parent && window.parent !== window && typeof window.parent.closeFormPopup === 'function';
            if (!inModal) {
                return;
            }

            form.addEventListener('submit', function (event) {
                event.preventDefault();

                var submitButton = form.querySelector('button[type="submit"]');
                if (submitButton) {
                    submitButton.disabled = true;
                }

                fetch(window.location.href, {
                    method: 'POST',
                    body: new FormData(form),
                    credentials: 'same-origin'
                }).then(function (response) {
                    if (!response.ok) {
                        if (submitButton) {
                            submitButton.disabled = false;
                        }
                        return;
                    }

                    window.parent.closeFormPopup();
                    window.parent.location.href = '/liste-bus-affectations/';
                }).catch(function () {
                    if (submitButton) {
                        submitButton.disabled = false;
                    }
                });
            });
        }

        return {
            init: init
        };
    })();

    var PopupFormBridge = (function () {
        function normalizePath(pathname) {
            if (!pathname) {
                return '/';
            }
            return pathname.endsWith('/') ? pathname : pathname + '/';
        }

        function getReturnUrl() {
            var params = new URLSearchParams(window.location.search);
            return params.get('return_to') || '';
        }

        function isPopupMode() {
            var params = new URLSearchParams(window.location.search);
            return params.get('popup') === '1';
        }

        function initCancelBridge(returnUrl) {
            document.addEventListener('click', function (event) {
                var explicitCancel = event.target.closest('[data-popup-cancel], .js-popup-cancel');

                if (explicitCancel) {
                    event.preventDefault();
                    window.parent.closeFormPopup();
                    window.parent.location.href = returnUrl;
                    return;
                }

                var link = event.target.closest('a[href]');
                if (!link) {
                    return;
                }

                var href = link.getAttribute('href') || '';
                if (!href) {
                    return;
                }

                try {
                    var target = new URL(href, window.location.origin);
                    var normalizedTargetPath = normalizePath(target.pathname);
                    var normalizedReturnPath = normalizePath(new URL(returnUrl, window.location.origin).pathname);

                    if (normalizedTargetPath === normalizedReturnPath) {
                        event.preventDefault();
                        window.parent.closeFormPopup();
                        window.parent.location.href = returnUrl;
                    }
                } catch (error) {
                    // Ignore malformed URL and allow default behavior.
                }
            });
        }

        function initSubmitBridge(returnUrl) {
            var form = document.querySelector('form[method="post"], form[method="POST"]');
            if (!form) {
                return;
            }

            // Use native iframe submission for popup forms so Django can render
            // field and non-field errors directly inside the iframe on validation failures.
            // Successful submissions still close via the parent iframe load listener after redirect.
            return;
        }

        function init() {
            if (!isPopupMode()) {
                return;
            }
            if (!(window.parent && window.parent !== window && typeof window.parent.closeFormPopup === 'function')) {
                return;
            }

            var returnUrl = getReturnUrl();
            if (!returnUrl) {
                return;
            }

            initCancelBridge(returnUrl);
            initSubmitBridge(returnUrl);
        }

        return {
            init: init
        };
    })();

    document.addEventListener('DOMContentLoaded', function () {
        PopupFormBridge.init();
        DeleteAffectationModal.init();

        if (hasPageClass('page-admin-dashboard')) {
            var restoreFn = AdminDashboard.restorePopupState;
            if (typeof restoreFn === 'function') {
                restoreFn();
            }
        }

        if (hasPageClass('page-student-home')) {
            StudentHome.init();
        }
        if (hasPageClass('page-driver-home')) {
            DriverHome.init();
        }
        if (hasPageClass('page-trajets-programmes')) {
            TrajetsProgrammes.init();
        }
        if (hasPageClass('page-liste-lignes')) {
            ListeLignes.init();
        }
        if (hasPageClass('page-ligne-form')) {
            LigneForm.init();
            StationFormset.init();
        }
        if (hasPageClass('page-remplissage-bus')) {
            RemplissageBus.init();
        }

        if (document.querySelector('form[method="get"]')) {
            FilterHighlight.init();
        }
    });

    document.addEventListener('keydown', function (event) {
        if (event.key !== 'Escape') {
            return;
        }

        if (hasPageClass('page-admin-dashboard')) {
            AdminDashboard.closeFormPopup();
            return;
        }

        if (isAdminShellPage()) {
            AdminShell.closeFormPopup();
            if (hasPageClass('page-liste-lignes')) {
                ListeLignes.closeAddLignePopup();
            }
        }
    });

    window.toggleDark = function (button) {
        if (hasPageClass('page-student-home')) {
            StudentHome.toggleDark(button);
            return;
        }
        if (hasPageClass('page-trajets-programmes')) {
            TrajetsProgrammes.toggleDark(button);
            return;
        }
        if (hasPageClass('page-admin-dashboard')) {
            AdminDashboard.toggleDark(button);
            return;
        }
        if (isAdminShellPage()) {
            AdminShell.toggleDark(button);
            return;
        }
        if (typeof legacy.toggleDark === 'function') {
            legacy.toggleDark(button);
        }
    };

    window.logout = function () {
        if (hasPageClass('page-student-home')) {
            StudentHome.logout();
            return;
        }
        if (hasPageClass('page-trajets-programmes')) {
            TrajetsProgrammes.logout();
            return;
        }
        if (hasPageClass('page-admin-dashboard')) {
            AdminDashboard.logout();
            return;
        }
        if (isAdminShellPage()) {
            AdminShell.logout();
            return;
        }
        if (typeof legacy.logout === 'function') {
            legacy.logout();
        }
    };

    window.showPanel = function (panelName, button) {
        if (hasPageClass('page-student-home')) {
            StudentHome.showPanel(panelName, button);
            return;
        }
        if (hasPageClass('page-admin-dashboard')) {
            AdminDashboard.showPanel(panelName, button);
            return;
        }
        if (typeof legacy.showPanel === 'function') {
            legacy.showPanel(panelName, button);
        }
    };

    window.showDriverPanel = function (panelName, button) {
        if (hasPageClass('page-driver-home')) {
            DriverHome.showDriverPanel(panelName, button);
            return;
        }
    };

    window.openFormPopup = function (url, title, iconClass) {
        if (hasPageClass('page-admin-dashboard')) {
            AdminDashboard.openFormPopup(url, title, iconClass);
            return;
        }
        if (hasPageClass('page-liste-lignes')) {
            ListeLignes.openFormPopup(url, title, iconClass);
            return;
        }
        if (isAdminShellPage()) {
            AdminShell.openFormPopup(url, title, iconClass);
            return;
        }
        if (typeof legacy.openFormPopup === 'function') {
            legacy.openFormPopup(url, title, iconClass);
        }
    };

    window.closeFormPopup = function () {
        if (hasPageClass('page-admin-dashboard')) {
            AdminDashboard.closeFormPopup();
            return;
        }
        if (hasPageClass('page-liste-lignes')) {
            ListeLignes.closeAddLignePopup();
            return;
        }
        if (isAdminShellPage()) {
            AdminShell.closeFormPopup();
            return;
        }
        if (typeof legacy.closeFormPopup === 'function') {
            legacy.closeFormPopup();
        }
    };

    window.openAddLignePopup = function () {
        if (hasPageClass('page-admin-dashboard')) {
            AdminDashboard.openAddLignePopup();
            return;
        }
        if (hasPageClass('page-liste-lignes')) {
            ListeLignes.openAddLignePopup();
            return;
        }
        if (typeof legacy.openAddLignePopup === 'function') {
            legacy.openAddLignePopup();
        }
    };

    window.closeAddLignePopup = function () {
        if (hasPageClass('page-liste-lignes')) {
            ListeLignes.closeAddLignePopup();
            return;
        }
        if (typeof legacy.closeAddLignePopup === 'function') {
            legacy.closeAddLignePopup();
        }
    };

    window.clearFilters = function () {
        if (isAdminShellPage()) {
            AdminShell.clearFilters();
            return;
        }
        if (typeof legacy.clearFilters === 'function') {
            legacy.clearFilters();
        }
    };

    window.updateFiltersColors = function () {
        if (hasPageClass('page-liste-lignes')) {
            ListeLignes.updateFiltersColors();
            return;
        }
        if (typeof legacy.updateFiltersColors === 'function') {
            legacy.updateFiltersColors();
        }
    };

    window.openDeleteModal = function (actionUrl, trajetLabel) {
        if (hasPageClass('page-bus-trajets')) {
            BusTrajets.openDeleteModal(actionUrl, trajetLabel);
            return;
        }
        if (typeof legacy.openDeleteModal === 'function') {
            legacy.openDeleteModal(actionUrl, trajetLabel);
        }
    };

    window.closeDeleteModal = function () {
        if (hasPageClass('page-bus-trajets')) {
            BusTrajets.closeDeleteModal();
            return;
        }
        if (typeof legacy.closeDeleteModal === 'function') {
            legacy.closeDeleteModal();
        }
    };

    window.reserveTrajet = function (btn) {
        if (hasPageClass('page-student-home')) {
            StudentHome.reserveTrajet(btn);
            return;
        }
        if (typeof legacy.reserveTrajet === 'function') {
            legacy.reserveTrajet(btn);
        }
    };

    window.cancelReservation = function (btnOrIndex) {
        if (hasPageClass('page-student-home')) {
            StudentHome.cancelReservation(btnOrIndex);
            return;
        }
        if (typeof legacy.cancelReservation === 'function') {
            legacy.cancelReservation(btnOrIndex);
        }
    };

    window.subscribeToLine = function () {
        if (hasPageClass('page-student-home')) {
            StudentHome.subscribeToLine();
            return;
        }
        if (typeof legacy.subscribeToLine === 'function') {
            legacy.subscribeToLine();
        }
    };

    window.unsubscribe = function (ligneId) {
        if (hasPageClass('page-student-home')) {
            StudentHome.unsubscribe(ligneId);
            return;
        }
        if (typeof legacy.unsubscribe === 'function') {
            legacy.unsubscribe(ligneId);
        }
    };

    window.rateTrip = function (btn) {
        if (hasPageClass('page-student-home')) {
            StudentHome.rateTrip(btn);
            return;
        }
        if (typeof legacy.rateTrip === 'function') {
            legacy.rateTrip(btn);
        }
    };

    window.closeRatingModal = function () {
        if (hasPageClass('page-student-home')) {
            StudentHome.closeRatingModal();
            return;
        }
        if (typeof legacy.closeRatingModal === 'function') {
            legacy.closeRatingModal();
        }
    };

    window.refreshFilterHighlights = FilterHighlight.refresh;
})();

/* ========================================================================
   RESPONSIVE: Hamburger drawer sidebar for mobile phones (≤ 480px)
   Injects a hamburger button and overlay into any page that has
   #appLayout > aside (all sidebar-based pages).
   CSS class .has-sidebar on <body> activates the responsive rules.
   ======================================================================== */
(function () {
    'use strict';

    function closeSidebar() {
        document.body.classList.remove('sidebar-open');
    }

    function toggleSidebar() {
        document.body.classList.toggle('sidebar-open');
    }

    document.addEventListener('DOMContentLoaded', function () {
        var appLayout = document.getElementById('appLayout');
        if (!appLayout) return;
        var aside = appLayout.querySelector(':scope > aside');
        if (!aside) return;

        // Mark body so hamburger CSS rules activate
        document.body.classList.add('has-sidebar');

        // Inject click-away overlay before aside
        var overlay = document.createElement('div');
        overlay.className = 'sidebar-overlay';
        overlay.addEventListener('click', closeSidebar);
        appLayout.insertBefore(overlay, appLayout.firstChild);

        // Inject hamburger button as first child of the header
        var header = appLayout.querySelector('.main-col header');
        if (header) {
            var btn = document.createElement('button');
            btn.className = 'hamburger-btn';
            btn.type = 'button';
            btn.setAttribute('aria-label', 'Ouvrir le menu');
            btn.innerHTML = '<i class="fas fa-bars"></i>';
            btn.addEventListener('click', toggleSidebar);
            header.insertBefore(btn, header.firstChild);
        }

        // Close sidebar when a nav link inside the drawer is clicked (mobile UX)
        aside.addEventListener('click', function (e) {
            if (e.target.closest('a, button:not(.hamburger-btn)')) {
                closeSidebar();
            }
        });
    });

    // Expose globally in case other code needs to close the drawer
    window.closeSidebar = closeSidebar;
    window.toggleSidebar = toggleSidebar;
}());

