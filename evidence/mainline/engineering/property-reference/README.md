# 一致物性工程参考

本包为完整设施运行器准备纯工质热力学数值参考，未运行设施效果试验、调度或训练。R134a只作具名研究替身；郑州实际冷媒仍未知。

- [冻结参考表](../../../../configs/materials/reference-r134a-saturation.json)：CoolProp 8.0.0 / HEOS / R134a / DEF，512点、0.1–3.0MPa、SI单位。
- [公开核验记录](finite-verification.json)：543离网点、25个M/U/V初值与外部EOS flash；数值门槛在作者脚本计算前声明。
- [接收收据](receipt.json)：参考表/脚本/压缩元数据及公开记录SHA；全512行h=u+p/ρ另由根代理读回核对。
- [模型骨架和手算参考](model-basis.md)：实际执行功率、服务缺额、两相与跨域边界。
- [作者程序原件](prepare_reference_properties.py)与[原始本地身份清单](reference-artifact-manifest.json)。清单中安装报告/二进制保留在作者Temp缓存，不代表已作为本包媒体公开。
- [PyPI元数据快照](pypi-metadata.json.gz)：解压后SHA见收据；冻结版本、wheel URL和SHA亦在参考表source段。

公开核验记录移除了作者本机模块绝对路径，其余数值结果保留；原始本地记录SHA在`curated_from_original_sha256`，不把整理后的JSON冒充原始字节。

## 消费与复现

运行器仅消费冻结JSON，无需安装CoolProp。ln(p)下插值T、v和u，再派生ρ与h；域外、混合物/不可凝气体和两相之外均需明确模型处理，不以裁剪伪造闭合。

作者程序是离线生成/核验工具，不应被运行器import。若需复现，将它复制到新的作者目录：解压元数据为`coolprop-pypi-metadata.json`，按表source中的URL取回并核对相同Windows Python3.12 ABI3 wheel，置于`wheels/`，用8.0.0在该目录的`coolprop-deps/`隔离安装（NumPy为既有2.3.5），然后运行作者程序。它会在作者目录重新生成表和有限验证记录，不覆盖主线运行原件。

核验说明同一EOS表的有限数值一致性，不是独立经验验证或郑州现场参数标定。全设施M1仍需实现和验收；此参考准备不单独完成任何物理/策略研究门槛。
