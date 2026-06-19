import streamlit as st
import pandas as pd
import psycopg2  # <-- Conexão com o Postgres/Neon

def conectar_banco():
    # Sua string de conexão com o banco Neon
    url_conexao = "postgresql://neondb_owner:npg_4fbN3iTzXmre@ep-plain-snow-atggseac.c-9.us-east-1.aws.neon.tech/neondb?sslmode=require"
    return psycopg2.connect(dsn=url_conexao)

st.set_page_config(page_title="Portal de Estoque", layout="wide")

# =========================================================
# SISTEMA DE AUTENTICAÇÃO (TELA DE LOGIN)
# =========================================================
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

def realizar_login(usuario, senha):
    # Credenciais padrão (pode alterar se quiser)
    if usuario == "admin" and senha == "vison123":
        st.session_state["autenticado"] = True
        st.success("Login realizado com sucesso!")
        st.rerun()
    else:
        st.error("Usuário ou senha incorretos.")

# Se NÃO está logado, mostra apenas a tela de login
if not st.session_state["autenticado"]:
    st.title("🔒 Acesso ao Sistema de Estoque")
    st.markdown("Por favor, insira suas credenciais para gerenciar o estoque da empresa.")
    
    with st.form("form_login"):
        campo_usuario = st.text_input("Usuário")
        campo_senha = st.text_input("Senha", type="password")
        botao_entrar = st.form_submit_button("Entrar no Sistema", use_container_width=True)
        
        if botao_entrar:
            realizar_login(campo_usuario, campo_senha)

# Se JÁ está logado, libera o sistema completo
else:
    # --- MENU LATERAL DE NAVEGAÇÃO ---
    st.sidebar.title("Navegação")
    menu = st.sidebar.radio("Selecione a Tela:", [
    "📈 Dashboard de Vendas", 
    "📦 Cadastrar Novo Produto", 
    "🚚 Entrada / Saída (Fluxo)", 
    "📅 Histórico de Auditoria"
])
    
    st.sidebar.markdown("---")
    if st.sidebar.button("🔴 Sair do Sistema", use_container_width=True):
        st.session_state["autenticado"] = False
        st.rerun()

    # =========================================================
    # TELA 1: DASHBOARD & ALERTAS (AGORA COM GRÁFICO!)
    # =========================================================
    if menu == "📊 Dashboard & Alertas":
        st.title("📊 Painel de Controle de Estoque")
        
        try:
            conn = conectar_banco()
            query = '''SELECT id AS "ID", nome AS "Produto", categoria AS "Categoria", quantidade_atual AS "Qtd Atual", estoque_minimo AS "Estoque Mínimo", preco_custo AS "Preço Custo", preco_venda AS "Preço Venda" FROM produtos'''
            df = pd.read_sql(query, conn)
            conn.close()
        except Exception as e:
            st.error(f"Erro ao conectar ao banco de dados: {e}")
            df = pd.DataFrame()

        if not df.empty:
            # Cards de resumo
            produtos_criticos = df[df['Qtd Atual'] <= df['Estoque Mínimo']]
            total_criticos = len(produtos_criticos)
            
            col1, col2 = st.columns(2)
            col1.metric("Total de Itens Cadastrados", len(df))
            col2.metric("Produtos em Alerta", total_criticos, delta=-total_criticos, delta_color="inverse" if total_criticos > 0 else "normal")
            
            if total_criticos > 0:
                st.error(f"⚠️ **Atenção:** Você tem {total_criticos} produto(s) abaixo ou no limite do estoque mínimo!")
                with st.expander("🔎 Ver lista de compras necessária"):
                    st.dataframe(produtos_criticos[['Produto', 'Qtd Atual', 'Estoque Mínimo']], hide_index=True)
            else:
                st.success("✅ Todos os produtos estão com níveis de estoque saudáveis!")

            # -----------------------------------------------------
            # 📈 NOVA SEÇÃO: GRÁFICO DOS TOP 5 MAIS VENDIDOS
            # -----------------------------------------------------
            st.markdown("---")
            st.subheader("🔥 Top 5 Produtos Mais Vendidos")
            
            try:
                conn = conectar_banco()
                query_top5 = """
                    SELECT p.nome AS "Produto", SUM(m.quantidade) AS "Total Vendido"
                    FROM movimentacoes m
                    INNER JOIN produtos p ON m.produto_id = p.id
                    WHERE m.tipo = 'SAÍDA'
                    GROUP BY p.nome
                    ORDER BY "Total Vendido" DESC
                    LIMIT 5
                """
                df_top5 = pd.read_sql(query_top5, conn)
                conn.close()
                
                if not df_top5.empty:
                    # Renderiza o gráfico de barras interativo do Streamlit
                    st.bar_chart(data=df_top5, x="Produto", y="Total Vendido", color="#ff4b4b")
                else:
                    st.info("Ainda não há registros de saídas/vendas suficientes para gerar o gráfico.")
            except Exception as e:
                st.error(f"Erro ao gerar gráfico de vendas: {e}")
            
            st.markdown("---")
            st.subheader("Todos os Produtos em Estoque")
            
            def colorir_criticos(row):
                return ['background-color: #ffcccc' if row['Qtd Atual'] <= row['Estoque Mínimo'] else '' for _ in row]
                
            df_formatado = df.style.format({
                'Preço Custo': 'R$ {:.2f}',
                'Preço Venda': 'R$ {:.2f}'
            }).apply(colorir_criticos, axis=1)
                
            st.dataframe(df_formatado, use_container_width=True, hide_index=True)

    # =========================================================
    # TELA 2: CADASTRAR PRODUTO
    # =========================================================
    elif menu == "➕ Cadastrar Produto":
        st.title("➕ Cadastro de Novos Produtos")
        
        with st.form("form_cadastro"):
            nome = st.text_input("Nome do Produto")
            categoria = st.text_input("Categoria")
            quantidade_inicial = st.number_input("Quantidade Inicial em Estoque", min_value=0, step=1)
            estoque_minimo = st.number_input("Estoque Mínimo (Alerta)", min_value=1, value=5, step=1)
            preco_custo = st.number_input("Preço de Custo (R$)", min_value=0.0, format="%.2f")
            preco_venda = st.number_input("Preço de Venda (R$)", min_value=0.0, format="%.2f")
            
            botao_cadastrar = st.form_submit_button("Salvar Produto")
            
            if botao_cadastrar:
                if nome:
                    try:
                        conn = conectar_banco()
                        cursor = conn.cursor()
                        sql = """INSERT INTO produtos (nome, categoria, quantidade_atual, estoque_minimo, preco_custo, preco_venda) 
                                 VALUES (%s, %s, %s, %s, %s, %s)"""
                        valores = (nome, categoria, quantidade_inicial, estoque_minimo, preco_custo, preco_venda)
                        cursor.execute(sql, valores)
                        conn.commit()
                        cursor.close()
                        conn.close()
                        st.success(f"Produto '{nome}' cadastrado com sucesso!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Erro ao salvar no banco: {e}")
                else:
                    st.warning("O nome do produto é obrigatório.")

        st.markdown("---")
        st.subheader("🗑️ Remover Produto do Sistema")
        try:
            conn = conectar_banco()
            df_deletar = pd.read_sql("SELECT id, nome FROM produtos", conn)
            conn.close()
        except Exception as e:
            df_deletar = pd.DataFrame()

        if not df_deletar.empty:
            lista_deletar = [f"{row['id']} - {row['nome']}" for _, row in df_deletar.iterrows()]
            produto_para_deletar = st.selectbox("Selecione o produto que deseja excluir permanentemente:", lista_deletar)
            botao_deletar = st.button("🔴 Excluir Produto Definitivamente", use_container_width=True)
            
            if botao_deletar:
                id_deletar = int(produto_para_deletar.split(" - ")[0])
                nome_deletar = produto_para_deletar.split(" - ")[1]
                try:
                    conn = conectar_banco()
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM movimentacoes WHERE produto_id = %s", (id_deletar,))
                    cursor.execute("DELETE FROM produtos WHERE id = %s", (id_deletar,))
                    conn.commit()
                    cursor.close()
                    conn.close()
                    st.success(f"Produto '{nome_deletar}' removido com sucesso!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao deletar produto: {e}")
        else:
            st.info("Nenhum produto cadastrado para remoção.")

    # =========================================================
    # TELA 3: ENTRADA/SAÍDA DE ESTOQUE
    # =========================================================
    elif menu == "🔄 Entrada/Saída de Estoque":
        st.title("🔄 Movimentação de Estoque (Entradas e Saídas)")
        
        try:
            conn = conectar_banco()
            df_produtos = pd.read_sql("SELECT id, nome, quantidade_atual FROM produtos", conn)
            conn.close()
        except Exception as e:
            st.error(f"Erro ao carregar produtos: {e}")
            df_produtos = pd.DataFrame()
            
        if not df_produtos.empty:
            lista_produtos = [f"{row['id']} - {row['nome']} (Atual: {row['quantidade_atual']})" for _, row in df_produtos.iterrows()]
            
            with st.form("form_movimentacao"):
                produto_selecionado = st.selectbox("Escolha o Produto:", lista_produtos)
                tipo_movimento = st.selectbox("Tipo de Operação:", ["ENTRADA", "SAÍDA"])
                qtd_movimentada = st.number_input("Quantidade:", min_value=1, step=1)
                
                botao_movimentar = st.form_submit_button("Confirmar Movimentação")
                
                if botao_movimentar:
                    id_produto = int(produto_selecionado.split(" - ")[0])
                    qtd_atual = int(df_produtos[df_produtos['id'] == id_produto]['quantidade_atual'].values[0])
                    
                    if tipo_movimento == "SAÍDA" and qtd_movimentada > qtd_atual:
                        st.error("Erro: Quantidade de saída maior do que a disponível em estoque!")
                    else:
                        try:
                            conn = conectar_banco()
                            cursor = conn.cursor()
                            sql_hist = "INSERT INTO movimentacoes (produto_id, tipo, quantidade) VALUES (%s, %s, %s)"
                            cursor.execute(sql_hist, (id_produto, tipo_movimento, qtd_movimentada))
                            
                            if tipo_movimento == "ENTRADA":
                                sql_update = "UPDATE produtos SET quantidade_atual = quantidade_atual + %s WHERE id = %s"
                            else:
                                sql_update = "UPDATE produtos SET quantidade_atual = quantidade_atual - %s WHERE id = %s"
                                
                            cursor.execute(sql_update, (qtd_movimentada, id_produto))
                            conn.commit()
                            cursor.close()
                            conn.close()
                            st.success("Estoque updated com sucesso!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro ao processar movimentação: {e}")
        else:
            st.warning("Nenhum produto cadastrado para movimentar.")

    # =========================================================
    # TELA 4: HISTÓRICO DE MOVIMENTAÇÕES
    # =========================================================
    elif menu == "📜 Histórico de Movimentações":
        st.title("📜 Histórico e Auditoria de Estoque")
        st.markdown("Veja tudo o que entrou e saiu do estoque com datas e horários.")
        
        try:
            conn = conectar_banco()
            query_hist = """
                SELECT m.id AS "Cód. Mov", p.nome AS "Produto", m.tipo AS "Operação", 
                       m.quantidade AS "Quantidade", 
                       TO_CHAR(m.data_movimentacao, 'DD/MM/YYYY HH24:MI') AS "Data/Hora"
                FROM movimentacoes m
                INNER JOIN produtos p ON m.produto_id = p.id
                ORDER BY m.data_movimentacao DESC
            """
            df_historico = pd.read_sql(query_hist, conn)
            conn.close()
        except Exception as e:
            st.error(f"Erro ao carregar histórico: {e}")
            df_historico = pd.DataFrame()
            
        if not df_historico.empty:
            st.dataframe(df_historico, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma movimentação (entrada ou saída) foi registrada ainda.")