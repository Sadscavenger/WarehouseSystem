from flask import Flask, render_template, request, redirect, url_for, send_file, jsonify, session
import pandas as pd
import os
from datetime import datetime
import shutil

app = Flask(__name__)
# 为了使用 session，需要设置一个密钥，实际应用中应使用更安全的密钥
app.secret_key = 'your_secret_key'

# 定义库存文件路径
INVENTORY_FILE = 'inventory.xlsx'
STATIC_DIR = app.static_folder

# 检查库存文件是否存在，如果不存在则创建一个空的 DataFrame
if not os.path.exists(INVENTORY_FILE):
    columns = ['款号', '颜色', '尺码', '入库时间', '库存数量', '出入库类型', '操作时间']
    df = pd.DataFrame(columns=columns)
    df.to_excel(INVENTORY_FILE, index=False)

# 将 enumerate 函数注入到 Jinja2 环境中
app.jinja_env.globals.update(enumerate=enumerate)

# 管理员用户名和密码（示例，实际应用中应使用更安全的方式存储）
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = '12345678'

# 登录页面路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            # 登录成功，将用户信息存入 session
            session['username'] = username
            # 登录成功，重定向到主页
            return redirect(url_for('index'))
        else:
            # 登录失败，返回登录页面并显示错误信息
            return render_template('login.html', error='用户名或密码错误')
    return render_template('login.html')

# 注销登录的路由
@app.route('/logout')
def logout():
    # 从 session 中移除用户信息
    session.pop('username', None)
    return redirect(url_for('login'))

# 定义一个 before_request 函数，用于在每个请求之前检查用户是否登录
@app.before_request
def before_request():
    # 对于登录页面和静态文件的请求，不进行登录检查
    if request.endpoint in ['login', 'static']:
        return
    # 如果用户未登录，重定向到登录页面
    if 'username' not in session:
        return redirect(url_for('login'))

# 首页路由，显示主页面
@app.route('/')
def index():
    df = pd.read_excel(INVENTORY_FILE)
    # 计算总库存
    total_inventory = df[df['出入库类型'] == '入库']['库存数量'].sum() - df[df['出入库类型'] == '出库']['库存数量'].sum()
    # 统计入库数量
    inbound_inventory = df[df['出入库类型'] == '入库']['库存数量'].sum()
    # 统计出库数量
    outbound_inventory = df[df['出入库类型'] == '出库']['库存数量'].sum()

    # 计算每个款式的剩余数量
    style_remaining = df.groupby('款号')['库存数量'].sum()

    # 将 Series 转换为字典，方便在模板中使用
    style_remaining_dict = style_remaining.to_dict()

    return render_template('index.html', total_inventory=total_inventory, inbound_inventory=inbound_inventory,
                           outbound_inventory=outbound_inventory, style_remaining=style_remaining_dict)

# 添加新库存的路由
@app.route('/add_inventory', methods=['GET', 'POST'])
def add_inventory():
    if request.method == 'POST':
        style_number = request.form['style_number']
        color = request.form['color']
        size = request.form['size']
        quantity = int(request.form['quantity'])
        # 获取当前时间作为入库时间
        entry_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        df = pd.read_excel(INVENTORY_FILE)
        new_row = pd.DataFrame([[style_number, color, size, entry_time, quantity, '入库', entry_time]],
                               columns=['款号', '颜色', '尺码', '入库时间', '库存数量', '出入库类型', '操作时间'])
        df = pd.concat([df, new_row], ignore_index=True)
        df.to_excel(INVENTORY_FILE, index=False)
        return redirect(url_for('display_records'))
    return render_template('add_inventory.html')

# 每页显示的记录数（默认值）
PER_PAGE = 10

# 显示出入库记录的路由，包含搜索、排序和分页功能
@app.route('/display_records')
def display_records():
    keyword = request.args.get('keyword')
    sort = request.args.get('sort')
    page = request.args.get('page', 1, type=int)
    # 获取每页显示数量，默认为 10
    per_page = request.args.get('per_page', PER_PAGE, type=int)

    df = pd.read_excel(INVENTORY_FILE)
    if keyword:
        # 模糊搜索逻辑，不区分大小写
        keyword = keyword.lower()
        df = df[
            (df['款号'].astype(str).str.lower().str.contains(keyword)) |
            (df['颜色'].astype(str).str.lower().str.contains(keyword)) |
            (df['尺码'].astype(str).str.lower().str.contains(keyword))
        ]
    if sort:
        df = df.sort_values(by=sort)

    # 计算总页数
    total_pages = (len(df) + per_page - 1) // per_page

    # 计算当前页的数据范围
    start = (page - 1) * per_page
    end = min(start + per_page, len(df))  # 确保end不超过数据长度
    records = df.iloc[start:end].to_dict(orient='records')

    return render_template('display_records.html', records=records, page=page, total_pages=total_pages, keyword=keyword, sort=sort, per_page=per_page)

# 出库功能的路由
@app.route('/remove_inventory', methods=['GET', 'POST'])
def remove_inventory():
    if request.method == 'POST':
        style_number = request.form['style_number']
        color = request.form['color']
        size = request.form['size']
        quantity = int(request.form['quantity'])

        df = pd.read_excel(INVENTORY_FILE)
        index = df[(df['款号'] == style_number) & (df['颜色'] == color) & (df['尺码'] == size)].index
        if len(index) > 0:
            current_quantity = df.loc[index[0], '库存数量']
            if current_quantity >= quantity:
                df.loc[index[0], '库存数量'] -= quantity
                # 记录出库记录
                entry_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                new_row = pd.DataFrame([[style_number, color, size, entry_time, quantity, '出库', entry_time]],
                                       columns=['款号', '颜色', '尺码', '入库时间', '库存数量', '出入库类型', '操作时间'])
                df = pd.concat([df, new_row], ignore_index=True)
            else:
                # 出库数量大于库存数量，记录负库存
                new_row = pd.DataFrame([[style_number, color, size, entry_time, quantity - current_quantity, '出库', entry_time]],
                                       columns=['款号', '颜色', '尺码', '入库时间', '库存数量', '出入库类型', '操作时间'])
                df = pd.concat([df, new_row], ignore_index=True)
                df.loc[index[0], '库存数量'] = 0
            df.to_excel(INVENTORY_FILE, index=False)
    return render_template('remove_inventory.html')

# 导入库存的路由
@app.route('/import_inventory', methods=['GET', 'POST'])
def import_inventory():
    if request.method == 'POST':
        file = request.files['file']
        if file and file.filename.endswith('.xlsx'):
            df = pd.read_excel(file)
            existing_df = pd.read_excel(INVENTORY_FILE)
            df = pd.concat([existing_df, df], ignore_index=True)
            df.to_excel(INVENTORY_FILE, index=False)
            return redirect(url_for('display_records'))
    return render_template('import_inventory.html')

# 导出库存的路由
@app.route('/export_inventory')
def export_inventory():
    # 复制库存文件到 static 目录
    shutil.copyfile(INVENTORY_FILE, os.path.join(STATIC_DIR, 'inventory.xlsx'))
    return render_template('export_inventory.html')

# 新增一个路由用于直接下载文件
@app.route('/download_inventory')
def download_inventory():
    return send_file(os.path.join(STATIC_DIR, 'inventory.xlsx'), as_attachment=True)

# 显示剩余库存的路由，包含库存预警功能
@app.route('/remaining_inventory')
def remaining_inventory():
    keyword = request.args.get('keyword')  # 获取搜索关键词

    df = pd.read_excel(INVENTORY_FILE)
    if keyword:
        # 模糊搜索逻辑，不区分大小写
        keyword = keyword.lower()
        df = df[
            (df['款号'].astype(str).str.lower().str.contains(keyword)) |
            (df['颜色'].astype(str).str.lower().str.contains(keyword)) |
            (df['尺码'].astype(str).str.lower().str.contains(keyword))
        ]

    # 按款号、颜色和尺码分组，分别统计入库和出库数量
    grouped = df.groupby(['款号', '颜色', '尺码', '出入库类型'])['库存数量'].sum().unstack(fill_value=0)
    grouped['剩余库存'] = grouped.get('入库', 0) - grouped.get('出库', 0)
    # 透视表，将尺码作为列
    pivot_df = grouped.reset_index().pivot_table(index=['款号', '颜色'], columns='尺码', values='剩余库存', fill_value=0).reset_index()
    
    # 确保包含所有尺码列
    size_columns = ['S', 'M', 'L', 'XL', 'XXL']
    for size in size_columns:
        if size not in pivot_df.columns:
            pivot_df[size] = 0

    # 按每个尺码的数量来预警，单尺码少于 20 件预警
    for size in size_columns:
        pivot_df[f'{size}_预警'] = pivot_df[size] < 20

    return render_template('remaining_inventory.html', inventory=pivot_df.to_dict(orient='records'), keyword=keyword)
# 修改库存信息的路由
@app.route('/edit_inventory/<int:index>', methods=['GET', 'POST'])
def edit_inventory(index):
    df = pd.read_excel(INVENTORY_FILE)
    if request.method == 'POST':
        df.loc[index, '款号'] = request.form['style_number']
        df.loc[index, '颜色'] = request.form['color']
        df.loc[index, '尺码'] = request.form['size']
        df.loc[index, '库存数量'] = int(request.form['quantity'])
        df.to_excel(INVENTORY_FILE, index=False)
        return redirect(url_for('display_records'))
    item = df.iloc[index].to_dict()
    return render_template('edit_inventory.html', item=item, index=index)

# 删除库存信息的路由
@app.route('/delete_inventory/<int:index>')
def delete_inventory(index):
    df = pd.read_excel(INVENTORY_FILE)
    df = df.drop(index)
    df = df.reset_index(drop=True)
    df.to_excel(INVENTORY_FILE, index=False)
    return redirect(url_for('display_records'))

# 批量删除记录的路由
@app.route('/batch_delete_records', methods=['POST'])
def batch_delete_records():
    selected_records = request.form.getlist('selected_records')
    try:
        selected_records = [int(i) for i in selected_records]
        df = pd.read_excel(INVENTORY_FILE)
        df = df.drop(selected_records)
        df = df.reset_index(drop=True)
        df.to_excel(INVENTORY_FILE, index=False)
        return redirect(url_for('display_records'))
    except Exception as e:
        print(f"Error deleting records: {e}")
        return "删除记录时出现错误，请重试。"

# 批量修改记录的路由
@app.route('/batch_edit_records', methods=['POST'])
def batch_edit_records():
    data = request.get_json()
    selected_indices = [int(i) for i in data['selectedIndices'].split(',')]
    new_style_number = data.get('newStyleNumber')
    new_color = data.get('newColor')
    new_size = data.get('newSize')
    new_quantity = data.get('newQuantity')

    df = pd.read_excel(INVENTORY_FILE)
    for index in selected_indices:
        if new_style_number:
            df.loc[index, '款号'] = new_style_number
        if new_color:
            df.loc[index, '颜色'] = new_color
        if new_size:
            df.loc[index, '尺码'] = new_size
        if new_quantity:
            df.loc[index, '库存数量'] = int(new_quantity)

    df.to_excel(INVENTORY_FILE, index=False)
    return jsonify({"message": "记录修改成功！"})

if __name__ == '__main__':
    app.run(debug=True)