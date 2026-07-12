import torch
import torch.nn.functional as F
import os
import random
import math

BLOCK_SIZE = 3
MODEL_PATH = "model.pt"
VOCAB_PATH = "vocab.pt"
MODEL_VERSION = 2  

EMBED_DIM = 15
N_HIDDEN = 300
BATCH_SIZE = 64
LEARNING_RATE = 0.05
NUM_ITERATIONS = 70000
LR_DECAY_EVERY = 25000
LR_DECAY_FACTOR = 0.5
MAX_GEN_LEN = 50


stoi = {}
itos = {}
c, w1, b1, w2, b2, bngain, bnbias, bnmean_running, bnstd_running = [None]*9


def _forward(xb, training=True):
    emb = c[xb]
    embcat = emb.view(emb.shape[0], -1)
    hpreact = embcat @ w1 + b1

    if training:
        bnmeani = hpreact.mean(0, keepdim=True)
        bnstdi = hpreact.std(0, keepdim=True)
        hpreact = bngain * (hpreact - bnmeani) / (bnstdi + 1e-5) + bnbias
        with torch.no_grad():
            global bnmean_running, bnstd_running
            bnmean_running = 0.999 * bnmean_running + 0.001 * bnmeani
            bnstd_running = 0.999 * bnstd_running + 0.001 * bnstdi
    else:
        hpreact = bngain * (hpreact - bnmean_running) / (bnstd_running + 1e-5) + bnbias

    h = torch.tanh(hpreact)
    logits = h @ w2 + b2
    return logits


def train_model(words):
    global stoi, itos, c, w1, b1, w2, b2, bngain, bnbias, bnmean_running, bnstd_running

    chars = sorted(list(set(''.join(words))))
    stoi = {s: i+1 for i, s in enumerate(chars)}
    stoi['<S>'] = 0
    itos = {i: s for s, i in stoi.items()}
    torch.save((stoi, itos, MODEL_VERSION), VOCAB_PATH)

    x, y = [], []
    for w in words:
        context = [0] * BLOCK_SIZE
        for ch in list(w) + ['<S>']:
            ix = stoi[ch]
            x.append(context)
            y.append(ix)
            context = context[1:] + [ix]
    x = torch.tensor(x)
    y = torch.tensor(y)

    # 80/10/10 split — train on 80% like the notebook
    random.seed(1234)
    shuffled = words[:]
    random.shuffle(shuffled)
    n_train = int(0.8 * len(shuffled))
    train_words = set(shuffled[:n_train])

    x_train, y_train = [], []
    for w in words:
        if w not in train_words:
            continue
        context = [0] * BLOCK_SIZE
        for ch in list(w) + ['<S>']:
            ix = stoi[ch]
            x_train.append(context)
            y_train.append(ix)
            context = context[1:] + [ix]
    x_train = torch.tensor(x_train)
    y_train = torch.tensor(y_train)

    g = torch.Generator().manual_seed(2345)
    c = torch.randn((len(itos), EMBED_DIM), generator=g) * 0.1
    w1 = torch.randn((BLOCK_SIZE * EMBED_DIM, N_HIDDEN), generator=g) * 0.01
    b1 = torch.randn(N_HIDDEN, generator=g) * 0.01
    w2 = torch.randn((N_HIDDEN, len(itos)), generator=g) * 0.01
    b2 = torch.randn(len(itos), generator=g) * 0
    bngain = torch.ones((1, N_HIDDEN))
    bnbias = torch.zeros((1, N_HIDDEN))
    bnmean_running = torch.zeros((1, N_HIDDEN))
    bnstd_running = torch.ones((1, N_HIDDEN))

    params = [c, w1, b1, w2, b2, bngain, bnbias]
    for p in params:
        p.requires_grad = True

    lr = LEARNING_RATE
    for k in range(NUM_ITERATIONS):
        if k > 0 and k % LR_DECAY_EVERY == 0:
            lr *= LR_DECAY_FACTOR

        ix = torch.randint(0, x_train.shape[0], (BATCH_SIZE,), generator=g)
        xb, yb = x_train[ix], y_train[ix]

        logits = _forward(xb, training=True)
        loss = F.cross_entropy(logits, yb)

        for p in params:
            p.grad = None
        loss.backward()
        for p in params:
            p.data += -lr * p.grad

        if k % 20000 == 0:
            print(f"  step {k:>6d} | loss {loss.item():.4f} | lr {lr:.5f}", flush=True)

    print(f"=> Training concluded with final loss: {loss.item():.4f}", flush=True)
    torch.save([c, w1, b1, w2, b2, bngain, bnbias, bnmean_running, bnstd_running], MODEL_PATH)


def load_or_train():
    global stoi, itos, c, w1, b1, w2, b2, bngain, bnbias, bnmean_running, bnstd_running

    needs_retrain = True
    if os.path.exists(MODEL_PATH) and os.path.exists(VOCAB_PATH):
        vocab_data = torch.load(VOCAB_PATH, weights_only=False)
        if len(vocab_data) == 3 and vocab_data[2] == MODEL_VERSION:
            print("=> Loading existing Makemore model & vocabulary...", flush=True)
            stoi, itos = vocab_data[0], vocab_data[1]
            params = torch.load(MODEL_PATH, weights_only=False)
            c, w1, b1, w2, b2, bngain, bnbias, bnmean_running, bnstd_running = params
            needs_retrain = False

    if needs_retrain:
        print("=> Training Makemore from fiction_clean.txt (improved hyperparameters)...", flush=True)
        words = open("fiction_clean.txt", "r", encoding="utf-8").read().splitlines()
        train_model(words)


def generate_titles_makemore(prefix, temperature, num_titles):
   
    results = []
    temp = max(0.1, float(temperature))

    for _ in range(num_titles * 2):
        out = []
        context = [0] * BLOCK_SIZE
        total_log_prob = 0.0

        if prefix:
            for ch in prefix:
                if ch in stoi:
                    ix = stoi[ch]
                    out.append(ix)
                    context = context[1:] + [ix]

        for _ in range(MAX_GEN_LEN):
            logits = _forward(torch.tensor([context]), training=False)
            logits = logits / temp
            probs = F.softmax(logits, dim=1)

            ix = torch.multinomial(probs, num_samples=1).item()
            total_log_prob += torch.log(probs[0, ix] + 1e-10).item()

            context = context[1:] + [ix]
            out.append(ix)

            if ix == 0:
                break

        title = ''.join(itos[i] for i in out[:-1] if i != 0)

        if not title:
            continue

        avg_log_prob = total_log_prob / max(1, len(out))
        confidence = min(99, int(math.exp(avg_log_prob) * 300))

        results.append({
            "title": title.strip(),
            "confidence": max(10, confidence)
        })

    return results



load_or_train()
