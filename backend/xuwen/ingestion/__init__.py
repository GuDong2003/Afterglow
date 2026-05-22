"""ingestion 子包：把原始聊天记录转为可入库的 chunks。

流水线：parser -> cleaner -> splitter -> chunker -> embedder -> importer
"""
