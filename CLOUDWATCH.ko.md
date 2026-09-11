**한국어** | [日本語](CLOUDWATCH.md)

# CloudWatch Agent 설정 가이드

EC2에 CloudWatch Agent를 깔아 **메모리·스왑·디스크**를 수집한다.
Datadog Agent와 나란히 돌려서, 같은 지표를 두 도구가 어떻게 다루는지 비교하는 것이 목적이다.

---

## 0. 왜 Agent가 필요한가

CloudWatch는 EC2의 메트릭을 **하이퍼바이저 밖에서** 봅니다. 그래서 알 수 있는 것에 한계가 있습니다.

| 지표 | Agent 없음 (기본) | Agent 있음 |
|---|---|---|
| CPUUtilization | ✅ | ✅ |
| NetworkIn / NetworkOut | ✅ | ✅ |
| DiskReadBytes (볼륨 I/O) | ✅ | ✅ |
| **메모리 사용률** | ❌ | ✅ |
| **디스크 사용률(파일시스템)** | ❌ | ✅ |
| **스왑 사용률** | ❌ | ✅ |

메모리와 파일시스템 사용률은 **OS 안에서만 알 수 있는 값**입니다. AWS는 가상 머신 밖에 있으니 볼 수 없습니다.
그래서 안에 프로그램(Agent)을 심어야 합니다. Datadog Agent를 깐 이유도 정확히 같습니다.

> 실제 사례: `docker compose build` 가 멈췄던 그 메모리 부족 사건은 **CloudWatch에 전혀 기록되지 않았습니다.**
> Agent를 깔면 다음부터는 그래프에 남습니다.

---

## 1. IAM 역할 만들기 (5분)

Agent가 CloudWatch에 데이터를 보낼 권한이 필요합니다. **액세스 키를 서버에 두지 말고 IAM 역할**을 씁니다.

콘솔 → IAM → 역할 → **역할 생성**

| 단계 | 값 |
|---|---|
| 신뢰할 수 있는 엔터티 | **AWS 서비스** |
| 사용 사례 | **EC2** |
| 권한 정책 | `CloudWatchAgentServerPolicy` 검색 → 체크 |
| 역할 이름 | `hyojin-ubuntu-cwagent-role` |

**역할 생성** 클릭.

### EC2에 붙이기

EC2 → 인스턴스 → `hyojin-ubuntu` 선택 → **작업** → **보안** → **IAM 역할 수정**
→ 방금 만든 역할 선택 → **IAM 역할 업데이트**

재부팅은 필요 없습니다. 즉시 적용됩니다.

> **왜 액세스 키가 아니라 역할인가**: 키는 파일에 적어둬야 하고, 유출되면 폐기·재발급이 필요합니다.
> IAM 역할은 EC2가 자동으로 임시 자격증명을 받아 쓰고 만료시킵니다. 서버에 비밀값이 남지 않습니다.

---

## 2. Agent 설치 (5분)

EC2에 접속해서:

```bash
cd ~
wget https://amazoncloudwatch-agent.s3.amazonaws.com/ubuntu/amd64/latest/amazon-cloudwatch-agent.deb
sudo dpkg -i -E ./amazon-cloudwatch-agent.deb
rm amazon-cloudwatch-agent.deb
```

설치 확인:

```bash
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -m ec2 -a status
```

`"status": "stopped"` 로 나옵니다. 설정을 안 줬으니 정상입니다.

---

## 3. 설정 파일 넣기 (2분)

이 저장소의 `cloudwatch/amazon-cloudwatch-agent.json` 을 EC2로 복사합니다.

```bash
sudo cp ~/name-compat/cloudwatch/amazon-cloudwatch-agent.json \
        /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
```

> 저장소를 EC2에 올리지 않았다면, 파일 내용을 `sudo nano` 로 직접 붙여넣어도 됩니다.

### 설정 파일이 하는 일

| 항목 | 값 | 이유 |
|---|---|---|
| `metrics_collection_interval` | 60초 | 기본값. 짧게 하면 요금이 늘어난다 |
| `namespace` | `CWAgent` | 콘솔에서 찾기 쉬운 기본 이름 |
| `append_dimensions` | InstanceId, InstanceType | 인스턴스 정보를 태그처럼 자동 부착 |
| 수집 항목 | mem / swap / disk(`/`) 3종만 | **커스텀 메트릭은 지표 개수당 과금** |

일부러 최소로 잡았습니다. `diskio`, `netstat`, `cpu` 상세까지 켜면 지표가 수십 개로 늘어납니다.
상세한 관찰은 Datadog이 이미 하고 있으니, CloudWatch에는 "기본이 못 주는 것"만 담았습니다.

---

## 4. 적용 및 기동 (1분)

```bash
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl \
  -a fetch-config -m ec2 -s \
  -c file:/opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json
```

`-s` 가 "설정을 읽고 바로 시작"입니다.

확인:

```bash
/opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -m ec2 -a status
```

`"status": "running"` 이면 성공입니다.

메모리 여유도 함께 봅니다 (t3.micro는 빡빡합니다):

```bash
free -m
```

Datadog Agent(200~300MB) + CloudWatch Agent(50~100MB)가 같이 돌아갑니다.
스왑 2GB를 붙여뒀으니 버티지만, `available` 이 계속 50MB 미만이면 CloudWatch Agent를 끄고
비교만 끝낸 뒤 정리하는 편이 낫습니다.

---

## 5. 콘솔에서 확인 (5분 대기)

CloudWatch → 메트릭 → 모든 메트릭 → **CWAgent** → `InstanceId, InstanceType`

| 지표 이름 | 의미 |
|---|---|
| `MemoryUtilization` | 메모리 사용률 % |
| `SwapUtilization` | 스왑 사용률 % — 0보다 크면 메모리 부족 신호 |
| `DiskUtilization` | 루트 볼륨 사용률 % |

첫 데이터는 1~5분 뒤에 나타납니다.

### 비교 실습

일부러 메모리를 쓰게 만들고 두 도구를 나란히 봅니다.

```bash
cd ~/name-compat
docker compose build --no-cache app     # 메모리를 많이 먹는 작업
```

빌드가 도는 동안:

| 도구 | 보는 곳 |
|---|---|
| CloudWatch | 메트릭 → CWAgent → `MemoryUtilization` |
| Datadog | Infrastructure → Host Map → `hyojin-ubuntu` → Memory |

**차이가 보이는 지점**

| | CloudWatch Agent | Datadog Agent |
|---|---|---|
| 수집 간격 | 60초 (기본) | 15초 |
| 그래프 반응 속도 | 완만 | 뾰족한 순간까지 보임 |
| 프로세스별 내역 | 없음 | Live Processes에서 어느 프로세스가 먹었는지 |
| 컨테이너별 내역 | 없음 | Containers에서 app/nginx/datadog 각각 |
| 설정 방법 | JSON 파일 + IAM 역할 | 환경변수 + API 키 |
| 과금 방식 | 지표 개수당 | 호스트당 |

**60초 간격이라는 게 실제로 체감됩니다.** 빌드처럼 몇십 초 만에 끝나는 메모리 급등은
CloudWatch에서는 1~2 포인트로 뭉개지고, Datadog에서는 봉우리가 뚜렷하게 보입니다.

---

## 6. 알람 걸어보기 (선택, 10분)

수집한 메모리 지표로 알람을 만들면 CloudWatch의 진가가 나옵니다.

CloudWatch → 경보 → **경보 생성**

| 단계 | 값 |
|---|---|
| 지표 선택 | CWAgent → `MemoryUtilization` (InstanceId = 내 인스턴스) |
| 통계 / 기간 | 평균 / 5분 |
| 조건 | 정적, 보다 큼, **85** |
| 알림 | 새 SNS 주제 생성 → 이름 `namecompat-alerts` → **내 이메일** |
| 경보 이름 | `hyojin-ubuntu-memory-high` |

만든 직후 **이메일로 확인 요청**이 옵니다. 링크를 눌러 승인해야 알림이 옵니다.

같은 방식으로 걸어둘 만한 것:

| 지표 | 임계값 |
|---|---|
| `DiskUtilization` | > 85% |
| EC2 `CPUUtilization` | > 80% (Agent 불필요, 기본 지표) |
| RDS `FreeStorageSpace` | < 2GB (Agent 불필요) |
| RDS `DatabaseConnections` | > 40 (Agent 불필요) |

RDS 지표는 Agent 없이도 있으니 지금 바로 걸 수 있습니다.

---

## 7. 정리 (다 해봤으면)

비교가 끝나고 메모리를 아끼려면:

```bash
sudo /opt/aws/amazon-cloudwatch-agent/bin/amazon-cloudwatch-agent-ctl -m ec2 -a stop
```

완전히 제거:

```bash
sudo dpkg -r amazon-cloudwatch-agent
```

IAM 역할은 남겨둬도 요금이 들지 않습니다. 나중에 다시 쓸 수 있습니다.

**커스텀 메트릭은 남아있는 동안 과금**되므로, 오래 안 쓸 거면 알람도 함께 지우는 편이 좋습니다.

---

## 8. 트러블슈팅

| 증상 | 원인 / 조치 |
|---|---|
| 콘솔에 `CWAgent` 네임스페이스가 안 보임 | 5분 대기. 그래도 없으면 IAM 역할이 EC2에 붙었는지 확인 |
| Agent가 `stopped` 로 돌아감 | 로그 확인: `sudo tail -50 /opt/aws/amazon-cloudwatch-agent/logs/amazon-cloudwatch-agent.log` |
| `Unable to retrieve credentials` | IAM 역할 미부착. EC2 → 작업 → 보안 → IAM 역할 수정 |
| JSON 파싱 에러 | 설정 파일의 쉼표·중괄호 확인. `python3 -m json.tool < 파일` 로 검증 |
| 메모리가 더 빡빡해짐 | 정상. Agent 2개가 도는 중. `free -m` 확인, 필요하면 7번으로 정리 |
| `region` 관련 에러 | 설정의 `"region": "ap-northeast-1"` 이 실제 리전과 같은지 |

---

## 9. 결론 — 두 도구를 어떻게 나눠 쓰나

직접 비교해보시면 이런 감이 옵니다.

| 상황 | 어느 쪽 |
|---|---|
| AWS 리소스의 상태·요금·한도 | **CloudWatch** (RDS·ELB·Lambda 등 AWS가 직접 아는 것) |
| 애플리케이션 안에서 무슨 일이 일어났는지 | **Datadog** (트레이스·로그·프로세스) |
| 알람만 간단히 걸고 싶다 | **CloudWatch** (SNS 이메일이 간편) |
| 원인을 파고들어야 한다 | **Datadog** (트레이스 → 스팬 → 로그로 이동) |
| 비용 | CloudWatch는 지표당 / Datadog은 호스트당 |

실무에서도 둘을 함께 씁니다. **CloudWatch는 AWS 인프라의 사실 기록**, **Datadog은 서비스 동작의 해석**
정도로 역할이 나뉩니다.
