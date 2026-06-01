// =================================================
// @author: MorningXu (morningxu1991@163.com)
// @version v1.0.0
// @date: 2025-05-29
// @brief: ECharts 初始化 + WebSocket 数据更新 + 仪表盘管理
// @copyright:
// ==================================================

/**
 * RK3588 性能监控仪表盘
 * 管理 WebSocket 连接、ECharts 图表实例、历史数据缓冲
 */

// 配色方案
const COLORS = [
    '#3498db', '#2ecc71', '#f1c40f', '#e74c3c',
    '#9b59b6', '#1abc9c', '#e67e22', '#34495e'
];

// 时间范围选项
const TIME_RANGES = [
    {label: '1分钟', value: 60},
    {label: '3分钟', value: 180},
    {label: '5分钟', value: 300},
    {label: '10分钟', value: 600},
];
const DEFAULT_RANGE_INDEX = 0;

/**
 * 仪表盘主类
 */
class Dashboard {
    constructor() {
        this.ws = null;
        this.reconnectTimer = null;
        this.pollTimer = null;       // HTTP 轮询定时器
        this.polling = false;        // 是否处于 HTTP 轮询模式
        this.charts = {};
        this.timeRange = TIME_RANGES[DEFAULT_RANGE_INDEX].value;
        this.historySize = this._calcHistorySize();
        this.history = {
            time: [],
            cpu: Array.from({length: 8}, () => []),
            cpuTotal: [],
            npu: Array.from({length: 3}, () => []),
            npuTotal: [],
            gpu: [],
            memUsed: [],
            memFree: [],
            ddr: [],
            diskUsed: [],
            diskFree: [],
            rga: {},
            rgaTotal: [],
            vpu: {},
        };
        this._prefillPlaceholders();
        this.init();
    }

    /** 初始化所有图表和 WebSocket */
    init() {
        this.initCharts();
        this.connectWs();
        this.bindEvents();
        this.bindPerformanceButtons();
    }

    /** 绑定事件 */
    bindEvents() {
        const input = document.getElementById('intervalInput');
        let debounce = null;
        input.addEventListener('change', () => {
            clearTimeout(debounce);
            debounce = setTimeout(() => {
                const val = Math.max(500, Math.min(10000, parseInt(input.value) || 1000));
                input.value = val;
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(JSON.stringify({type: 'set_interval', value: val}));
                }
                // 轮询模式下间隔会在下一轮自动生效，无需额外操作
                // 刷新间隔变化时重新计算窗口大小
                this._changeTimeRange(this.timeRange);
            }, 300);
        });

        // 时间范围选择器
        const timeRangeSelect = document.getElementById('timeRangeSelect');
        timeRangeSelect.addEventListener('change', () => {
            this._changeTimeRange(parseInt(timeRangeSelect.value));
        });

        // 窗口大小变化时自适应
        window.addEventListener('resize', () => {
            Object.values(this.charts).forEach(c => c && c.resize());
        });
    }

    /** 初始化所有 ECharts 图表 */
    initCharts() {
        this.charts.cpu = this._createChart('cpuChart');
        this.charts.npu = this._createChart('npuChart');
        this.charts.gpu = this._createChart('gpuChart');
        this.charts.mem = this._createChart('memChart');
        this.charts.ddr = this._createChart('ddrChart');
        this.charts.disk = this._createChart('diskChart');
        this.charts.rga = this._createChart('rgaChart');
        this.charts.vpu = this._createChart('vpuChart');
    }

    /**
     * 创建 ECharts 实例
     * @param {string} domId - DOM 元素 ID
     * @returns {Object} ECharts 实例
     */
    _createChart(domId) {
        const dom = document.getElementById(domId);
        if (!dom) return null;
        return echarts.init(dom, 'dark');
    }

    /** 建立 WebSocket 连接 */
    connectWs() {
        const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${location.host}/ws`;
        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
            this._updateStatus('connected');
            // WS 连接成功，停止轮询（如果之前在轮询的话）
            this._stopPolling();
            // 发送当前间隔配置
            const val = parseInt(document.getElementById('intervalInput').value) || 1000;
            this.ws.send(JSON.stringify({type: 'set_interval', value: val}));
        };

        this.ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === 'data') {
                    this.onData(msg.data);
                } else if (msg.type === 'config') {
                    document.getElementById('intervalInput').value = msg.interval;
                }
            } catch (e) {
                console.error('解析消息失败:', e);
            }
        };

        this.ws.onclose = () => {
            this._updateStatus('disconnected');
            // 启动轮询回退
            this._startPolling();
            // 继续尝试 WS 重连
            this._scheduleReconnect();
        };

        this.ws.onerror = () => {
            this._updateStatus('disconnected');
            // 启动轮询回退
            this._startPolling();
        };
    }

    /** 3 秒后自动重连 */
    _scheduleReconnect() {
        clearTimeout(this.reconnectTimer);
        this.reconnectTimer = setTimeout(() => this.connectWs(), 3000);
    }

    /**
     * 启动 HTTP 轮询模式
     * 使用 /api/snapshot 接口定时拉取数据
     */
    _startPolling() {
        if (this.polling) return;
        this.polling = true;
        console.log('WebSocket 不可用，切换到 HTTP 轮询模式');
        this._updateStatus('polling');

        const poll = async () => {
            if (!this.polling) return;
            try {
                const resp = await fetch('/api/snapshot');
                if (!this.polling) return; // 可能在等待响应期间已停止
                const data = await resp.json();
                this.onData(data);
            } catch (e) {
                console.warn('HTTP 轮询请求失败:', e);
            }
            if (this.polling) {
                const interval = parseInt(document.getElementById('intervalInput').value) || 1000;
                this.pollTimer = setTimeout(poll, interval);
            }
        };

        // 立即执行一次
        poll();
    }

    /** 停止 HTTP 轮询 */
    _stopPolling() {
        this.polling = false;
        if (this.pollTimer) {
            clearTimeout(this.pollTimer);
            this.pollTimer = null;
        }
    }

    /**
     * 更新连接状态指示
     * @param {string} state - 状态：'connected' | 'disconnected' | 'polling'
     */
    _updateStatus(state) {
        const dot = document.getElementById('statusDot');
        const text = document.getElementById('statusText');
        dot.classList.remove('connected', 'polling');
        switch (state) {
            case 'connected':
                dot.classList.add('connected');
                text.textContent = '已连接';
                break;
            case 'polling':
                dot.classList.add('polling');
                text.textContent = '轮询中';
                break;
            default:
                text.textContent = '已断开';
                break;
        }
    }

    /**
     * 处理接收到的数据
     * @param {Object} data - 指标数据
     */
    onData(data) {
        const timeLabel = new Date().toLocaleTimeString('zh-CN', {hour12: false});

        // 更新历史缓冲（时间标签使用占位符查找替换）
        this._pushArray(this.history.time, timeLabel);
        this._updateCpuHistory(data.cpu);
        this._updateNpuHistory(data.npu);
        this._pushHistory('gpu', data.gpu ? data.gpu.load : null);
        this._updateMemHistory(data.memory);
        this._pushHistory('ddr', data.memory ? data.memory.ddr_frequency : null);
        this._updateDiskHistory(data.disk);
        this._updateRgaHistory(data.rga);
        this._updateVpuHistory(data.vpu);

        // 更新图表
        this._updateCpuChart(data.cpu);
        this._updateNpuChart(data.npu);
        this._updateGpuChart(data.gpu);
        this._updateMemChart(data.memory);
        this._updateDdrChart(data.memory);
        this._updateDiskChart(data.disk);
        this._updateRgaChart(data.rga);
        this._updateVpuChart(data.vpu);

        // 更新卡片标题
        this._updateTitles(data);

        // 更新汇总表格
        this._updateSummaryTable(data);
    }

    // ---- 历史数据管理 ----

    /** 绑定性能模式按钮事件 */
    bindPerformanceButtons() {
        const buttons = [
            {id: 'btnPerfCpu', endpoint: '/api/performance/cpu', label: 'CPU'},
            {id: 'btnPerfGpu', endpoint: '/api/performance/gpu', label: 'GPU'},
            {id: 'btnPerfNpu', endpoint: '/api/performance/npu', label: 'NPU'},
            {id: 'btnPerfAll', endpoint: '/api/performance/all', label: '全部'},
        ];
        buttons.forEach(({id, endpoint, label}) => {
            const btn = document.getElementById(id);
            if (btn) {
                btn.addEventListener('click', () => this._setPerformanceMode(btn, endpoint, label));
            }
        });
    }

    /**
     * 发送性能模式切换请求
     * @param {HTMLElement} btn - 按钮元素
     * @param {string} endpoint - API 端点
     * @param {string} label - 设备标签
     */
    async _setPerformanceMode(btn, endpoint, label) {
        const originalText = btn.textContent;
        btn.classList.add('loading');
        btn.textContent = '切换中...';
        btn.disabled = true;

        try {
            const resp = await fetch(endpoint, {method: 'POST'});
            const data = await resp.json();
            if (data.success) {
                btn.classList.remove('loading');
                btn.classList.add('success');
                if (data.performance) {
                    btn.textContent = '性能模式';
                    this._showToast(`${label} 已切换为性能模式`, 'success');
                } else {
                    btn.textContent = '已恢复';
                    this._showToast(`${label} 已恢复默认模式`, 'success');
                }
            } else {
                btn.classList.remove('loading');
                btn.classList.add('error');
                btn.textContent = '失败';
                this._showToast(`${label} 切换失败`, 'error');
            }
        } catch (e) {
            btn.classList.remove('loading');
            btn.classList.add('error');
            btn.textContent = '失败';
            this._showToast(`${label} 切换失败: ${e.message}`, 'error');
        }

        setTimeout(() => {
            btn.classList.remove('success', 'error', 'loading');
            btn.textContent = originalText;
            btn.disabled = false;
        }, 2000);
    }

    /**
     * 显示 Toast 提示
     * @param {string} message - 提示文本
     * @param {string} type - 类型：'success' 或 'error'
     */
    _showToast(message, type) {
        const container = document.getElementById('toastContainer');
        if (!container) return;
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        // 触发动画
        requestAnimationFrame(() => toast.classList.add('show'));
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    /**
     * 向历史缓冲推入一个值，超过窗口大小时移除最早的
     */
    _pushHistory(key, value) {
        const arr = this.history[key];
        if (Array.isArray(arr)) {
            this._pushArray(arr, value);
        }
    }

    /**
     * 根据时间范围和刷新间隔计算历史窗口大小
     * @returns {number} 窗口大小
     */
    _calcHistorySize() {
        const interval = parseInt(document.getElementById('intervalInput').value) || 1000;
        return Math.ceil(this.timeRange * 1000 / interval);
    }

    /** 预填占位符，使x轴从一开始就显示完整范围 */
    _prefillPlaceholders() {
        const size = this.historySize;
        this.history.time = Array(size).fill('');
        this.history.cpuTotal = Array(size).fill(null);
        this.history.npuTotal = Array(size).fill(null);
        this.history.gpu = Array(size).fill(null);
        this.history.memUsed = Array(size).fill(null);
        this.history.memFree = Array(size).fill(null);
        this.history.ddr = Array(size).fill(null);
        this.history.diskUsed = Array(size).fill(null);
        this.history.diskFree = Array(size).fill(null);
        for (let i = 0; i < 8; i++) {
            this.history.cpu[i] = Array(size).fill(null);
        }
        for (let i = 0; i < 3; i++) {
            this.history.npu[i] = Array(size).fill(null);
        }
        this.history.rga = {};
        this.history.rgaTotal = Array(size).fill(null);
        this.history.vpu = {};
    }

    /**
     * 切换时间范围
     * @param {number} seconds - 新的时间范围（秒）
     */
    _changeTimeRange(seconds) {
        this.timeRange = seconds;
        this.historySize = this._calcHistorySize();
        this._prefillPlaceholders();
    }

    /**
     * 带占位符查找的数组推入：找到第一个占位符替换，否则 shift+push
     * @param {Array} arr - 目标数组
     * @param {*} value - 要推入的值
     */
    _pushArray(arr, value) {
        // 查找第一个占位符位置（null 或 空字符串）
        const idx = arr.findIndex(v => v === null || v === '');
        if (idx !== -1) {
            arr[idx] = value;
        } else {
            // 所有占位符已被替换，执行滑动窗口
            arr.shift();
            arr.push(value);
        }
    }

    _updateCpuHistory(cpu) {
        if (!cpu) return;
        if (cpu.total_usage !== null && cpu.total_usage !== undefined) {
            this._pushHistory('cpuTotal', cpu.total_usage);
        }
        if (cpu.core_usage) {
            cpu.core_usage.forEach((v, i) => {
                if (v !== null && v !== undefined && this.history.cpu[i]) {
                    this._pushArray(this.history.cpu[i], v);
                }
            });
        }
    }

    _updateNpuHistory(npu) {
        if (!npu) return;
        if (npu.total_load !== null && npu.total_load !== undefined) {
            this._pushHistory('npuTotal', npu.total_load);
        }
        if (npu.core_load) {
            npu.core_load.forEach((v, i) => {
                if (v !== null && v !== undefined && this.history.npu[i]) {
                    this._pushArray(this.history.npu[i], v);
                }
            });
        }
    }

    _updateMemHistory(mem) {
        if (!mem) return;
        this._pushHistory('memUsed', mem.used_mib);
        this._pushHistory('memFree', mem.free_mib);
    }

    _updateDiskHistory(disk) {
        if (!disk) return;
        this._pushHistory('diskUsed', disk.used_gib);
        this._pushHistory('diskFree', disk.free_gib);
    }

    _updateRgaHistory(rga) {
        if (!rga) return;
        // 总负载
        if (rga.load != null) {
            this._pushHistory('rgaTotal', rga.load);
        }
        // 各 core 负载
        if (rga.core_loads) {
            rga.core_loads.forEach(c => {
                if (!this.history.rga[c.name]) {
                    this.history.rga[c.name] = Array(this.historySize).fill(null);
                }
                this._pushArray(this.history.rga[c.name], c.load);
            });
        }
    }

    _updateVpuHistory(vpu) {
        if (!vpu) return;
        const all = [...(vpu.encoders || []), ...(vpu.decoders || [])];
        all.forEach(v => {
            if (!this.history.vpu[v.name]) {
                this.history.vpu[v.name] = Array(this.historySize).fill(null);
            }
            this._pushArray(this.history.vpu[v.name], v.frequency);
        });
    }

    // ---- 图表更新方法 ----

    /** 基础面积/折线图 option 生成 */
    _baseAreaOption(title, series, yAxisUnit) {
        // 计算x轴标签间隔，保持约8个可见标签
        const labelInterval = Math.max(0, Math.floor(this.history.time.length / 8) - 1);
        return {
            backgroundColor: 'transparent',
            animation: true,
            animationDuration: 300,
            animationEasing: 'linear',
            grid: {left: 50, right: 16, top: 16, bottom: 24},
            tooltip: {trigger: 'axis', appendToBody: true},
            legend: {
                textStyle: {color: '#a0a0b0', fontSize: 11},
                top: 0, right: 0,
                itemWidth: 14, itemHeight: 10,
            },
            xAxis: {
                type: 'category',
                data: this.history.time,
                axisLabel: {color: '#606080', fontSize: 10, interval: labelInterval},
                axisLine: {lineStyle: {color: '#2a2a4a'}},
            },
            yAxis: {
                type: 'value',
                axisLabel: {color: '#606080', fontSize: 10},
                axisLine: {lineStyle: {color: '#2a2a4a'}},
                splitLine: {lineStyle: {color: '#1e1e3a'}},
            },
            series: series,
        };
    }


    _updateCpuChart(cpu) {
        if (!this.charts.cpu) return;
        const series = [];
        for (let i = 0; i < 8; i++) {
            const s = {
                name: `CPU${i}`,
                type: 'line',
                stack: 'cpu',
                areaStyle: {opacity: 0.3},
                lineStyle: {width: 1},
                symbol: 'none',
                data: this.history.cpu[i],
                itemStyle: {color: COLORS[i % COLORS.length]},
            };
            series.push(s);
        }
        this.charts.cpu.setOption(this._baseAreaOption('CPU', series, '%'), true);
    }

    _updateNpuChart(npu) {
        if (!this.charts.npu) return;
        const series = [];
        for (let i = 0; i < 3; i++) {
            const s = {
                name: `NPU${i}`,
                type: 'line',
                stack: 'npu',
                areaStyle: {opacity: 0.3},
                lineStyle: {width: 1},
                symbol: 'none',
                data: this.history.npu[i],
                itemStyle: {color: COLORS[i % COLORS.length]},
            };
            series.push(s);
        }
        this.charts.npu.setOption(this._baseAreaOption('NPU', series, '%'), true);
    }

    _updateGpuChart(gpu) {
        if (!this.charts.gpu || !gpu) return;
        const series = [{
            name: 'GPU',
            type: 'line',
            areaStyle: {opacity: 0.4, color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                {offset: 0, color: '#2ecc71'}, {offset: 1, color: 'rgba(46,204,113,0.1)'}
            ])},
            lineStyle: {width: 2, color: '#2ecc71'},
            symbol: 'none',
            data: this.history.gpu,
            itemStyle: {color: '#2ecc71'},
        }];
        this.charts.gpu.setOption(this._baseAreaOption('GPU', series, '%'), true);
    }

    _updateMemChart(mem) {
        if (!this.charts.mem) return;
        const series = [
            {
                name: 'Used',
                type: 'line',
                stack: 'mem',
                areaStyle: {opacity: 0.3},
                lineStyle: {width: 1},
                symbol: 'none',
                data: this.history.memUsed,
                itemStyle: {color: COLORS[0]},
            },
            {
                name: 'Free',
                type: 'line',
                stack: 'mem',
                areaStyle: {opacity: 0.3},
                lineStyle: {width: 1},
                symbol: 'none',
                data: this.history.memFree,
                itemStyle: {color: COLORS[1]},
            },
        ];
        this.charts.mem.setOption(this._baseAreaOption('Memory', series, 'MiB'), true);
    }

    _updateDdrChart(mem) {
        if (!this.charts.ddr) return;
        const series = [{
            name: 'DDR',
            type: 'line',
            lineStyle: {width: 2, color: COLORS[7]},
            symbol: 'none',
            data: this.history.ddr,
            itemStyle: {color: COLORS[7]},
        }];
        this.charts.ddr.setOption(this._baseAreaOption('DDR', series, 'MHz'), true);
    }

    _updateDiskChart(disk) {
        if (!this.charts.disk) return;
        const used = disk ? disk.used_gib : null;
        const free = disk ? disk.free_gib : null;
        const option = {
            backgroundColor: 'transparent',
            animation: true,
            animationDuration: 300,
            animationEasing: 'linear',
            grid: {left: 60, right: 30, top: 20, bottom: 30},
            tooltip: {trigger: 'axis', axisPointer: {type: 'shadow'}, appendToBody: true},
            legend: {
                textStyle: {color: '#a0a0b0', fontSize: 11},
                top: 0,
            },
            xAxis: {
                type: 'value',
                axisLabel: {color: '#606080', fontSize: 10},
                axisLine: {lineStyle: {color: '#2a2a4a'}},
                splitLine: {lineStyle: {color: '#1e1e3a'}},
            },
            yAxis: {
                type: 'category',
                data: ['Disk'],
                axisLabel: {color: '#606080', fontSize: 10},
                axisLine: {lineStyle: {color: '#2a2a4a'}},
            },
            series: [
                {
                    name: 'Used',
                    type: 'bar',
                    stack: 'disk',
                    data: [used],
                    itemStyle: {color: COLORS[0]},
                    barWidth: 30,
                    label: {
                        show: true,
                        position: 'inside',
                        formatter: (p) => p.value != null ? `${p.value} GiB` : 'N/A',
                        color: '#fff',
                        fontSize: 11,
                    },
                },
                {
                    name: 'Free',
                    type: 'bar',
                    stack: 'disk',
                    data: [free],
                    itemStyle: {color: COLORS[1]},
                    barWidth: 30,
                    label: {
                        show: true,
                        position: 'inside',
                        formatter: (p) => p.value != null ? `${p.value} GiB` : 'N/A',
                        color: '#fff',
                        fontSize: 11,
                    },
                },
            ],
        };
        this.charts.disk.setOption(option, true);
    }

    _updateRgaChart(rga) {
        if (!this.charts.rga) return;
        const labels = Object.keys(this.history.rga);
        if (labels.length === 0 && (!rga || !rga.load)) {
            // 完全无数据
            return;
        }
        const series = [];
        labels.forEach((label, idx) => {
            series.push({
                name: label,
                type: 'line',
                lineStyle: {width: 1.5},
                symbol: 'none',
                data: this.history.rga[label],
                itemStyle: {color: COLORS[idx % COLORS.length]},
            });
        });
        if (series.length === 0) {
            // 仅 devfreq 模式有总负载无 core_loads
            series.push({
                name: 'RGA',
                type: 'line',
                areaStyle: {opacity: 0.4, color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                    {offset: 0, color: '#e67e22'}, {offset: 1, color: 'rgba(230,126,34,0.1)'}
                ])},
                lineStyle: {width: 2, color: '#e67e22'},
                symbol: 'none',
                data: this.history.rgaTotal,
                itemStyle: {color: '#e67e22'},
            });
        }
        this.charts.rga.setOption(this._baseAreaOption('RGA', series, '%'), true);
    }

    _updateVpuChart(vpu) {
        if (!this.charts.vpu || !vpu) return;
        const series = [];
        const labels = Object.keys(this.history.vpu);
        labels.forEach((label, idx) => {
            series.push({
                name: label,
                type: 'line',
                lineStyle: {width: 1.5},
                symbol: 'none',
                data: this.history.vpu[label],
                itemStyle: {color: COLORS[idx % COLORS.length]},
            });
        });
        if (series.length === 0) {
            // 无 VPU 数据时显示提示
            this.charts.vpu.setOption({
                backgroundColor: 'transparent',
                graphic: {
                    type: 'text',
                    left: 'center',
                    top: 'center',
                    style: {text: 'VPU 不可用', fill: '#606080', fontSize: 14},
                },
            }, true);
        } else {
            this.charts.vpu.setOption(this._baseAreaOption('VPU', series, 'MHz'), true);
        }
    }

    // ---- 卡片标题更新 ----

    /**
     * 从 thermal 数据中查找匹配关键字的温度
     * @param {Object} thermal - thermal 数据
     * @param {string} keyword - 关键字（如 "GPU"、"A76"）
     * @returns {string|null} 温度字符串或 null
     */
    _findTemp(thermal, keyword) {
        if (!thermal || !thermal.sensors) return null;
        const s = thermal.sensors.find(s => s.label.toUpperCase().includes(keyword.toUpperCase()));
        return s && s.temperature != null ? `${s.temperature}°C` : null;
    }

    _updateTitles(data) {
        // CPU
        const cpuTotal = data.cpu && data.cpu.total_usage != null ? `${data.cpu.total_usage}%` : 'N/A';
        const cpuTemp = this._findTemp(data.thermal, 'A76') || this._findTemp(data.thermal, 'cpu');
        document.getElementById('cpuTitle').textContent = cpuTemp ? `${cpuTotal} (${cpuTemp})` : cpuTotal;

        // NPU
        const npuTotal = data.npu && data.npu.total_load != null ? `${data.npu.total_load}%` : 'N/A';
        document.getElementById('npuTitle').textContent = npuTotal;

        // GPU
        const gpuLoad = data.gpu && data.gpu.load != null ? `${data.gpu.load}%` : 'N/A';
        const gpuTemp = this._findTemp(data.thermal, 'GPU');
        document.getElementById('gpuTitle').textContent = gpuTemp ? `${gpuLoad} (${gpuTemp})` : gpuLoad;

        // Memory
        const memPct = data.memory && data.memory.usage_percent != null
            ? `${data.memory.usage_percent}%` : 'N/A';
        const memUsed = data.memory && data.memory.used_mib != null
            ? `${data.memory.used_mib} MiB` : '';
        document.getElementById('memTitle').textContent = memUsed ? `${memPct} (${memUsed})` : memPct;

        // DDR
        const ddrFreq = data.memory && data.memory.ddr_frequency != null
            ? `${data.memory.ddr_frequency} MHz` : 'N/A';
        document.getElementById('ddrTitle').textContent = ddrFreq;

        // Disk
        const diskPct = data.disk && data.disk.usage_percent != null
            ? `${data.disk.usage_percent}%` : 'N/A';
        const diskUsed = data.disk && data.disk.used_gib != null
            ? `${data.disk.used_gib} GiB` : '';
        document.getElementById('diskTitle').textContent = diskUsed ? `${diskPct} (${diskUsed})` : diskPct;

        // RGA
        const rgaLoad = data.rga && data.rga.load != null ? `${data.rga.load}%` : 'N/A';
        const rgaFreq = data.rga && data.rga.frequency != null ? ` (${data.rga.frequency} MHz)` : '';
        const rgaCores = data.rga && data.rga.core_loads && data.rga.core_loads.length > 0
            ? ` [${data.rga.core_loads.map(c => `${c.name}:${c.load}%`).join(' ')}]` : '';
        document.getElementById('rgaTitle').textContent = `${rgaLoad}${rgaFreq}${rgaCores}`;

        // VPU
        const vpuAll = data.vpu ? [...(data.vpu.encoders || []), ...(data.vpu.decoders || [])] : [];
        if (vpuAll.length > 0) {
            const freqs = vpuAll.map(v => v.frequency != null ? `${v.frequency}` : 'N/A').join(' / ');
            document.getElementById('vpuTitle').textContent = `${freqs} MHz`;
        } else {
            document.getElementById('vpuTitle').textContent = 'N/A';
        }
    }

    // ---- 汇总表格更新 ----

    _updateSummaryTable(data) {
        const items = [];

        // CPU
        const cpuUsage = data.cpu || {};
        items.push({label: 'CPU_Total', value: cpuUsage.total_usage != null ? `${cpuUsage.total_usage}%` : 'N/A', cls: 'cpu-cell'});
        for (let i = 0; i < 8; i++) {
            const v = cpuUsage.core_usage && cpuUsage.core_usage[i] != null
                ? `${cpuUsage.core_usage[i]}%` : 'N/A';
            items.push({label: `CPU${i}`, value: v, cls: 'cpu-cell'});
        }

        // CPU 频率
        if (cpuUsage.frequencies) {
            cpuUsage.frequencies.forEach((f, i) => {
                items.push({label: `CPU_Freq${i}`, value: f != null ? `${f} MHz` : 'N/A', cls: 'cpu-cell'});
            });
        }

        // NPU
        const npuData = data.npu || {};
        items.push({label: 'NPU_Total', value: npuData.total_load != null ? `${npuData.total_load}%` : 'N/A', cls: 'npu-cell'});
        if (npuData.core_load) {
            npuData.core_load.forEach((v, i) => {
                items.push({label: `NPU${i}`, value: v != null ? `${v}%` : 'N/A', cls: 'npu-cell'});
            });
        }
        items.push({label: 'NPU_Freq', value: npuData.frequency != null ? `${npuData.frequency} MHz` : 'N/A', cls: 'npu-cell'});

        // GPU
        const gpuData = data.gpu || {};
        items.push({label: 'GPU', value: gpuData.load != null ? `${gpuData.load}%` : 'N/A', cls: 'gpu-cell'});
        items.push({label: 'GPU_Freq', value: gpuData.frequency != null ? `${gpuData.frequency} MHz` : 'N/A', cls: 'gpu-cell'});

        // Memory
        const memData = data.memory || {};
        items.push({label: 'Mem', value: memData.usage_percent != null ? `${memData.usage_percent}%` : 'N/A', cls: 'mem-cell'});
        items.push({label: 'DDR', value: memData.ddr_frequency != null ? `${memData.ddr_frequency} MHz` : 'N/A', cls: 'ddr-cell'});

        // Disk
        const diskData = data.disk || {};
        items.push({label: 'Disk', value: diskData.usage_percent != null ? `${diskData.usage_percent}%` : 'N/A', cls: 'disk-cell'});

        // RGA
        const rgaData = data.rga || {};
        items.push({label: 'RGA', value: rgaData.load != null ? `${rgaData.load}%` : 'N/A', cls: 'rga-cell'});
        items.push({label: 'RGA_Freq', value: rgaData.frequency != null ? `${rgaData.frequency} MHz` : 'N/A', cls: 'rga-cell'});
        if (rgaData.core_loads) {
            rgaData.core_loads.forEach(c => {
                items.push({label: `RGA(${c.name})`, value: c.load != null ? `${c.load}%` : 'N/A', cls: 'rga-cell'});
            });
        }

        // VPU
        const vpuAll = data.vpu ? [...(data.vpu.encoders || []), ...(data.vpu.decoders || [])] : [];
        vpuAll.forEach(v => {
            items.push({label: `VPU(${v.name})`, value: v.frequency != null ? `${v.frequency} MHz` : 'N/A', cls: 'vpu-cell'});
        });

        // Temperature
        const thermalData = data.thermal || {};
        if (thermalData.sensors) {
            thermalData.sensors.forEach(s => {
                const temp = s.temperature != null ? `${s.temperature}°C` : 'N/A';
                items.push({label: `Temp(${s.label})`, value: temp, cls: 'thermal-cell'});
            });
        }

        // 渲染到单个容器
        const row = document.getElementById('summaryRow');
        row.innerHTML = items.map(it =>
            `<div class="summary-item"><div class="summary-label">${it.label}</div><div class="summary-value ${it.cls}">${it.value}</div></div>`
        ).join('');
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new Dashboard();
});
