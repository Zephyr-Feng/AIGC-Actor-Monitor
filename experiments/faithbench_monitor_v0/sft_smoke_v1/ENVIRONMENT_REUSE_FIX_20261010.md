# 环境准备修正：复用已安装依赖与官方轮子

原PyPI完整解析/下载在18203实例的实际轮子速率约10KB/s，12MB Transformers数分钟只到1.5MB，会超出试跑准备时段。终止自有pip5984，原setup5976退出与日志、new venv/下载半成品保留。不是训练失败，未加载8B/停27B。

只读复制Actor已核验版本的transformers4.57.4、accelerate1.10.1、tokenizers0.22.2、huggingface-hub0.36.2、safetensors0.8.0及regex/hf-xet依赖的发行版文件到独立新venv；来源文件hash与复制文件核对，Actor路径不写入，运行只用新venv和共享base torch。只安装PEFT0.17.1/bitsandbytes0.50.0官方PyPI轮子，--no-deps以免重新解析/下载torch。

本机PEFT504896字节SHA `3d129d64def3d74779c32a080d2567e5f7b674e77d546e3585138216d903f99e`。bitsandbytes预期40860117字节SHA `173d137610468bec9cddbaa2e049254e97792657ab984e3e737bec1772c1668c`；首个完整请求实际截为8781824字节，未装，半成品保留。改用显式Range、校验每块范围/长度、再核对全文件SHA后才部署。此修正不改变数据、模型、训练或评价条件。
